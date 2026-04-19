use std::sync::Arc;
use tauri::Manager;
use tokio::process::Command;
use tokio::time::{sleep, Duration};

#[tokio::main]
async fn main() {
    let child: Arc<tokio::sync::Mutex<Option<tokio::process::Child>>> =
        Arc::new(tokio::sync::Mutex::new(None));

    let child_for_ready = child.clone();
    let child_for_exit = child.clone();
    let rt_handle = tokio::runtime::Handle::current();

    let app = tauri::Builder::default()
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |app_handle, event| {
        match event {
            tauri::RunEvent::Ready => {
                let child = child_for_ready.clone();
                let app_handle = app_handle.clone();
                tokio::spawn(async move {
                    // Determine Python executable path
                    let python_path = {
                        let cwd = std::env::current_dir().unwrap_or_default();
                        let venv_cwd = cwd.join(".venv/bin/python3");
                        let venv_bundle = std::env::current_exe()
                            .ok()
                            .and_then(|p| p.parent().map(|d| d.join(".venv/bin/python3")))
                            .unwrap_or_default();

                        if venv_cwd.exists() {
                            venv_cwd.to_string_lossy().into_owned()
                        } else if venv_bundle.exists() {
                            venv_bundle.to_string_lossy().into_owned()
                        } else if std::process::Command::new("python3")
                            .arg("--version")
                            .output()
                            .is_ok()
                        {
                            "python3".to_string()
                        } else {
                            "python".to_string()
                        }
                    };

                    eprintln!("[keyd-remapper] Using Python: {}", python_path);

                    let mut cmd = Command::new(&python_path);
                    cmd.arg("backend/main.py")
                        .env("KEYD_PORT", "8474")
                        .kill_on_drop(true);

                    match cmd.spawn() {
                        Ok(process) => {
                            let pid = process.id().unwrap_or(0);
                            eprintln!("[keyd-remapper] Started backend process with pid {}", pid);
                            {
                                let mut lock = child.lock().await;
                                *lock = Some(process);
                            }

                            // Poll backend until ready
                            let client = reqwest::Client::new();
                            let url = "http://127.0.0.1:8474/api/keyd/status";
                            let mut ready = false;
                            for attempt in 1..=60 {
                                sleep(Duration::from_millis(500)).await;
                                match client.get(url).send().await {
                                    Ok(resp) if resp.status().is_success() => {
                                        eprintln!(
                                            "[keyd-remapper] Backend ready (attempt {})",
                                            attempt
                                        );
                                        ready = true;
                                        break;
                                    }
                                    Ok(resp) => {
                                        eprintln!(
                                            "[keyd-remapper] Backend returned status {} (attempt {})",
                                            resp.status(),
                                            attempt
                                        );
                                    }
                                    Err(e) => {
                                        eprintln!(
                                            "[keyd-remapper] Backend not ready yet: {} (attempt {})",
                                            e, attempt
                                        );
                                    }
                                }
                            }

                            if ready {
                                if let Some(window) = app_handle.get_webview_window("main") {
                                    match tauri::Url::parse("http://127.0.0.1:8474") {
                                        Ok(url) => {
                                            if let Err(e) = window.navigate(url) {
                                                eprintln!(
                                                    "[keyd-remapper] Failed to navigate window: {}",
                                                    e
                                                );
                                            } else {
                                                eprintln!(
                                                    "[keyd-remapper] Navigated main window to backend"
                                                );
                                            }
                                        }
                                        Err(e) => {
                                            eprintln!(
                                                "[keyd-remapper] Failed to parse URL: {}",
                                                e
                                            );
                                        }
                                    }
                                } else {
                                    eprintln!("[keyd-remapper] Main window not found");
                                }
                            } else {
                                eprintln!(
                                    "[keyd-remapper] Backend did not become ready within 30 seconds"
                                );
                            }
                        }
                        Err(e) => {
                            eprintln!("[keyd-remapper] Failed to start backend: {}", e);
                        }
                    }
                });
            }
            tauri::RunEvent::ExitRequested { .. } => {
                let child = child_for_exit.clone();
                let handle = rt_handle.clone();
                std::thread::spawn(move || {
                    handle.block_on(async move {
                        let mut lock = child.lock().await;
                        if let Some(mut c) = lock.take() {
                            let _ = c.start_kill();
                            let _ = c.wait().await;
                            eprintln!("[keyd-remapper] Backend process killed on exit");
                        }
                    });
                })
                .join()
                .unwrap();
            }
            _ => {}
        }
    });
}

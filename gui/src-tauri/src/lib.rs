use security_framework::passwords::{
    delete_generic_password, get_generic_password, set_generic_password,
};

/// Store a credential in the macOS Keychain.
#[tauri::command]
fn store_credential(service: &str, account: &str, password: &str) -> Result<(), String> {
    // Delete any existing entry first (set_generic_password fails if it already exists)
    let _ = delete_generic_password(service, account);
    set_generic_password(service, account, password.as_bytes())
        .map_err(|e| format!("Failed to store credential: {e}"))
}

/// Retrieve a credential from the macOS Keychain.
/// Returns None if the credential does not exist.
#[tauri::command]
fn get_credential(service: &str, account: &str) -> Result<Option<String>, String> {
    match get_generic_password(service, account) {
        Ok(bytes) => {
            let s = String::from_utf8(bytes).map_err(|e| format!("Invalid UTF-8: {e}"))?;
            Ok(Some(s))
        }
        Err(e) => {
            // errSecItemNotFound (-25300) means no credential stored — not an error
            if e.code() == -25300 {
                Ok(None)
            } else {
                Err(format!("Failed to retrieve credential: {e}"))
            }
        }
    }
}

/// Delete a credential from the macOS Keychain.
/// Silently succeeds if the credential does not exist.
#[tauri::command]
fn delete_credential(service: &str, account: &str) -> Result<(), String> {
    match delete_generic_password(service, account) {
        Ok(()) => Ok(()),
        Err(e) => {
            if e.code() == -25300 {
                Ok(()) // Not found — nothing to delete
            } else {
                Err(format!("Failed to delete credential: {e}"))
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            store_credential,
            get_credential,
            delete_credential,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

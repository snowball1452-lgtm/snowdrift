package com.snowdrift

import android.content.Context
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

object PythonDaemonManager {

    private const val TAG = "PythonDaemon"
    private var started = false
    private var launcher: com.chaquo.python.PyObject? = null

    fun start(context: Context) {
        if (started) {
            Log.d(TAG, "Daemon already running — skipping")
            return
        }
        started = true

        CoroutineScope(Dispatchers.IO).launch {
            try {
                // Boot Chaquopy once
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(context))
                    Log.i(TAG, "Python runtime started")
                }

                val py = Python.getInstance()

                // Pass Android storage paths into the Python environment
                val filesDir   = context.filesDir.absolutePath
                val storeDir   = "$filesDir/sovereign_memory"
                val dotenvPath = "$filesDir/.env"

                // Load the daemon module and push env vars through a Python helper
                // (PyObject lacks a Kotlin __setitem__ bridge — use a helper function instead)
                launcher = py.getModule("daemon_launcher")
                launcher?.callAttr("set_env", "SOVEREIGN_STORE_DIR", storeDir)
                launcher?.callAttr("set_env", "APP_FILES_DIR",       filesDir)
                launcher?.callAttr("set_env", "DOTENV_PATH",         dotenvPath)

                Log.i(TAG, "Storage paths → $storeDir")

                // Launch the daemon (blocks internally — servers auto-restart on crash)
                launcher?.callAttr("launch")

            } catch (e: Exception) {
                Log.e(TAG, "Daemon start failed: ${e.message}", e)
                started = false
            }
        }
    }

    fun stop() {
        try {
            launcher?.callAttr("stop")
            Log.i(TAG, "Daemon stop requested")
        } catch (e: Exception) {
            Log.w(TAG, "Error stopping daemon: ${e.message}")
        }
        started = false
    }
}

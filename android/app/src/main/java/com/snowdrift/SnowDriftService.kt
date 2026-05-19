package com.snowdrift

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.IOException

/**
 * Background service for polling device actions when accessibility service isn't running.
 * The accessibility service handles most polling, but this is a backup.
 */
class SnowDriftService : Service() {
    
    companion object {
        private const val TAG = "SnowDriftService"
        private const val NOTIFICATION_ID = 1001
    }
    
    private val client = OkHttpClient()
    private val gson = Gson()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var pollingJob: Job? = null
    
    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "SnowDrift Service created")
    }
    
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.d(TAG, "SnowDrift Service started")
        startForeground(NOTIFICATION_ID, createNotification())
        startPolling()
        return START_STICKY
    }
    
    override fun onBind(intent: Intent?): IBinder? = null
    
    override fun onDestroy() {
        super.onDestroy()
        pollingJob?.cancel()
        scope.cancel()
        PythonDaemonManager.stop()
        Log.d(TAG, "SnowDrift Service destroyed")
    }
    
    private fun createNotification(): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent, PendingIntent.FLAG_IMMUTABLE
        )
        
        return NotificationCompat.Builder(this, SnowDriftApp.CHANNEL_ID)
            .setContentTitle("SnowDrift Running")
            .setContentText("Your AI assistant is active")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }
    
    private fun startPolling() {
        pollingJob = scope.launch {
            while (isActive) {
                // Only poll if accessibility service isn't running
                if (!SnowDriftAccessibilityService.isRunning) {
                    try {
                        fetchAndQueueActions()
                    } catch (e: Exception) {
                        Log.e(TAG, "Polling error: ${e.message}")
                    }
                }
                delay(5000) // Poll every 5 seconds
            }
        }
    }
    
    private suspend fun fetchAndQueueActions() {
        val backendUrl = BuildConfig.BACKEND_URL
        
        val request = Request.Builder()
            .url("$backendUrl/api/device-actions/pending?target=phone")
            .get()
            .build()
        
        try {
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    Log.d(TAG, "Fetched actions: $body")
                    // Actions will be handled by accessibility service when it starts
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "Network error: ${e.message}")
        }
    }
}

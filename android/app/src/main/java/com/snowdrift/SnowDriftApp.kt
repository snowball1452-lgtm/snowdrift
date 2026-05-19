package com.snowdrift

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class SnowDriftApp : Application() {
    
    companion object {
        const val CHANNEL_ID = "snowdrift_service"
        const val CHANNEL_NAME = "SnowDrift Service"
        
        lateinit var instance: SnowDriftApp
            private set
    }
    
    override fun onCreate() {
        super.onCreate()
        instance = this
        createNotificationChannel()
        // Start the frozen Python daemon as early as possible
        PythonDaemonManager.start(this)
    }
    
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "SnowDrift background service"
            }
            
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }
}

package com.moltbot

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.os.Build

class MoltBotApp : Application() {
    
    companion object {
        const val CHANNEL_ID = "moltbot_service"
        const val CHANNEL_NAME = "MoltBot Service"
        
        lateinit var instance: MoltBotApp
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
                description = "MoltBot background service"
            }
            
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }
}

package com.snowdrift

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

class BootReceiver : BroadcastReceiver() {
    
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            Log.d("SnowDrift", "Boot completed - SnowDrift will start when Accessibility Service is enabled")
            // The accessibility service will start automatically if enabled
        }
    }
}

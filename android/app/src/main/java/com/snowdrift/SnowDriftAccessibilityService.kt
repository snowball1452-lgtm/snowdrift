package com.snowdrift

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.*
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.IOException

class SnowDriftAccessibilityService : AccessibilityService() {
    
    companion object {
        private const val TAG = "SnowDriftA11y"
        var instance: SnowDriftAccessibilityService? = null
            private set
        
        var isRunning = false
            private set
        
        // Current screen state
        var currentPackage: String = ""
        var currentActivity: String = ""
        var screenContent: String = ""
    }
    
    private val client = OkHttpClient()
    private val gson = Gson()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var pollingJob: Job? = null
    
    // Backend URL from BuildConfig
    private val backendUrl: String
        get() = BuildConfig.BACKEND_URL
    
    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        isRunning = true
        Log.d(TAG, "Accessibility Service connected - SnowDrift has FULL phone control!")
        
        // Start polling for device actions
        startPolling()
        
        // Register as phone agent
        registerAgent()
    }
    
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        event?.let {
            // Track current app/screen
            it.packageName?.let { pkg -> currentPackage = pkg.toString() }
            it.className?.let { cls -> currentActivity = cls.toString() }
            
            // Update screen content on window changes
            if (event.eventType == AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED ||
                event.eventType == AccessibilityEvent.TYPE_WINDOW_CONTENT_CHANGED) {
                updateScreenContent()
            }
        }
    }
    
    override fun onInterrupt() {
        Log.d(TAG, "Accessibility Service interrupted")
    }
    
    override fun onDestroy() {
        super.onDestroy()
        instance = null
        isRunning = false
        pollingJob?.cancel()
        scope.cancel()
        Log.d(TAG, "Accessibility Service destroyed")
    }
    
    // ==================== SCREEN READING ====================
    
    private fun updateScreenContent() {
        rootInActiveWindow?.let { root ->
            screenContent = extractText(root)
        }
    }
    
    private fun extractText(node: AccessibilityNodeInfo, depth: Int = 0): String {
        val sb = StringBuilder()
        
        // Get text from this node
        node.text?.let { 
            sb.append("  ".repeat(depth))
            sb.append(it.toString())
            sb.append("\n")
        }
        
        node.contentDescription?.let {
            sb.append("  ".repeat(depth))
            sb.append("[${it}]")
            sb.append("\n")
        }
        
        // Recurse into children
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { child ->
                sb.append(extractText(child, depth + 1))
            }
        }
        
        return sb.toString()
    }
    
    fun getScreenInfo(): Map<String, Any> {
        return mapOf(
            "package" to currentPackage,
            "activity" to currentActivity,
            "content" to screenContent.take(2000) // Limit size
        )
    }
    
    // ==================== UI AUTOMATION ====================
    
    fun tap(x: Int, y: Int, callback: ((Boolean) -> Unit)? = null) {
        val path = Path().apply {
            moveTo(x.toFloat(), y.toFloat())
        }
        
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()
        
        dispatchGesture(gesture, object : GestureResultCallback() {
            override fun onCompleted(gestureDescription: GestureDescription?) {
                Log.d(TAG, "Tap completed at ($x, $y)")
                callback?.invoke(true)
            }
            override fun onCancelled(gestureDescription: GestureDescription?) {
                Log.d(TAG, "Tap cancelled")
                callback?.invoke(false)
            }
        }, null)
    }
    
    fun swipe(startX: Int, startY: Int, endX: Int, endY: Int, duration: Long = 300) {
        val path = Path().apply {
            moveTo(startX.toFloat(), startY.toFloat())
            lineTo(endX.toFloat(), endY.toFloat())
        }
        
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, duration))
            .build()
        
        dispatchGesture(gesture, null, null)
    }
    
    fun findAndClick(text: String): Boolean {
        rootInActiveWindow?.let { root ->
            val node = findNodeByText(root, text)
            if (node != null) {
                val rect = Rect()
                node.getBoundsInScreen(rect)
                tap(rect.centerX(), rect.centerY())
                return true
            }
        }
        return false
    }
    
    private fun findNodeByText(node: AccessibilityNodeInfo, text: String): AccessibilityNodeInfo? {
        if (node.text?.toString()?.contains(text, ignoreCase = true) == true ||
            node.contentDescription?.toString()?.contains(text, ignoreCase = true) == true) {
            return node
        }
        
        for (i in 0 until node.childCount) {
            node.getChild(i)?.let { child ->
                findNodeByText(child, text)?.let { return it }
            }
        }
        
        return null
    }
    
    fun inputText(text: String): Boolean {
        rootInActiveWindow?.let { root ->
            val focusedNode = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
            if (focusedNode != null) {
                val args = Bundle()
                args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
                focusedNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
                return true
            }
        }
        return false
    }
    
    fun pressBack() {
        performGlobalAction(GLOBAL_ACTION_BACK)
    }
    
    fun pressHome() {
        performGlobalAction(GLOBAL_ACTION_HOME)
    }
    
    fun openNotifications() {
        performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
    }
    
    fun openRecents() {
        performGlobalAction(GLOBAL_ACTION_RECENTS)
    }
    
    // ==================== POLLING & EXECUTION ====================
    
    private fun startPolling() {
        pollingJob = scope.launch {
            while (isActive) {
                try {
                    fetchAndExecuteActions()
                } catch (e: Exception) {
                    Log.e(TAG, "Polling error: ${e.message}")
                }
                delay(3000) // Poll every 3 seconds
            }
        }
    }
    
    private suspend fun fetchAndExecuteActions() {
        val request = Request.Builder()
            .url("$backendUrl/api/device-actions/pending?target=phone")
            .get()
            .build()
        
        try {
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string() ?: "[]"
                    val type = object : TypeToken<List<Map<String, Any>>>() {}.type
                    val actions: List<Map<String, Any>> = gson.fromJson(body, type)
                    
                    for (action in actions) {
                        executeAction(action)
                    }
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "Network error: ${e.message}")
        }
    }
    
    private suspend fun executeAction(action: Map<String, Any>) {
        val actionId = action["id"] as? String ?: return
        val actionType = action["action"] as? String ?: return
        val params = (action["params"] as? Map<String, Any>) ?: emptyMap()
        
        Log.d(TAG, "Executing action: $actionType with params: $params")
        
        val result = when (actionType) {
            "tap" -> {
                val x = (params["x"] as? Double)?.toInt() ?: 0
                val y = (params["y"] as? Double)?.toInt() ?: 0
                tap(x, y)
                mapOf("success" to true, "message" to "Tapped at ($x, $y)")
            }
            "swipe" -> {
                val startX = (params["startX"] as? Double)?.toInt() ?: 0
                val startY = (params["startY"] as? Double)?.toInt() ?: 0
                val endX = (params["endX"] as? Double)?.toInt() ?: 0
                val endY = (params["endY"] as? Double)?.toInt() ?: 0
                swipe(startX, startY, endX, endY)
                mapOf("success" to true, "message" to "Swiped from ($startX,$startY) to ($endX,$endY)")
            }
            "click_text" -> {
                val text = params["text"] as? String ?: ""
                val found = findAndClick(text)
                mapOf("success" to found, "message" to if (found) "Clicked '$text'" else "Text '$text' not found")
            }
            "input_text" -> {
                val text = params["text"] as? String ?: ""
                val success = inputText(text)
                mapOf("success" to success, "message" to if (success) "Text entered" else "No input field focused")
            }
            "press_back" -> {
                pressBack()
                mapOf("success" to true, "message" to "Pressed back")
            }
            "press_home" -> {
                pressHome()
                mapOf("success" to true, "message" to "Pressed home")
            }
            "get_screen" -> {
                mapOf("success" to true, "message" to "Screen info retrieved", "data" to getScreenInfo())
            }
            "open_app" -> {
                val packageName = params["package"] as? String ?: params["app"] as? String ?: ""
                openApp(packageName)
                mapOf("success" to true, "message" to "Opening $packageName")
            }
            else -> {
                // Fall back to basic phone actions (alarm, sms, etc.)
                executeBasicAction(actionType, params)
            }
        }
        
        // Report completion
        reportCompletion(actionId, result)
    }
    
    private fun executeBasicAction(actionType: String, params: Map<String, Any>): Map<String, Any> {
        return when (actionType) {
            "set_alarm" -> {
                val time = params["time"] as? String ?: ""
                val title = params["title"] as? String ?: "SnowDrift Alarm"
                PhoneActions.setAlarm(this, time, title)
            }
            "send_sms" -> {
                val phone = params["phone"] as? String ?: ""
                val message = params["message"] as? String ?: ""
                PhoneActions.sendSMS(this, phone, message)
            }
            "make_call" -> {
                val phone = params["phone"] as? String ?: ""
                PhoneActions.makeCall(this, phone)
            }
            else -> mapOf("success" to false, "message" to "Unknown action: $actionType")
        }
    }
    
    private fun openApp(packageName: String) {
        try {
            val intent = packageManager.getLaunchIntentForPackage(packageName)
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                startActivity(intent)
            } else {
                // Try common app mapping
                val mappedPackage = mapAppName(packageName)
                packageManager.getLaunchIntentForPackage(mappedPackage)?.let {
                    it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    startActivity(it)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open app: ${e.message}")
        }
    }
    
    private fun mapAppName(name: String): String {
        return when (name.lowercase()) {
            "spotify" -> "com.spotify.music"
            "whatsapp" -> "com.whatsapp"
            "youtube" -> "com.google.android.youtube"
            "chrome" -> "com.android.chrome"
            "maps" -> "com.google.android.apps.maps"
            "gmail" -> "com.google.android.gm"
            "calendar" -> "com.google.android.calendar"
            "clock" -> "com.google.android.deskclock"
            "camera" -> "com.android.camera2"
            "settings" -> "com.android.settings"
            "messages" -> "com.google.android.apps.messaging"
            "phone" -> "com.google.android.dialer"
            "contacts" -> "com.google.android.contacts"
            "photos" -> "com.google.android.apps.photos"
            "drive" -> "com.google.android.apps.docs"
            "twitter", "x" -> "com.twitter.android"
            "instagram" -> "com.instagram.android"
            "facebook" -> "com.facebook.katana"
            "telegram" -> "org.telegram.messenger"
            "netflix" -> "com.netflix.mediaclient"
            else -> name
        }
    }
    
    private suspend fun reportCompletion(actionId: String, result: Map<String, Any>) {
        val json = gson.toJson(result)
        val body = json.toRequestBody("application/json".toMediaType())
        
        val request = Request.Builder()
            .url("$backendUrl/api/device-actions/$actionId/complete")
            .post(body)
            .build()
        
        try {
            client.newCall(request).execute().close()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to report completion: ${e.message}")
        }
    }
    
    private fun registerAgent() {
        scope.launch {
            val agentInfo = mapOf(
                "name" to "android-${android.os.Build.MODEL}",
                "agent_type" to "phone",
                "capabilities" to listOf(
                    "tap", "swipe", "click_text", "input_text",
                    "press_back", "press_home", "get_screen",
                    "open_app", "set_alarm", "send_sms", "make_call"
                ),
                "metadata" to mapOf(
                    "model" to android.os.Build.MODEL,
                    "manufacturer" to android.os.Build.MANUFACTURER,
                    "os" to "Android ${android.os.Build.VERSION.RELEASE}"
                )
            )
            
            val json = gson.toJson(agentInfo)
            val body = json.toRequestBody("application/json".toMediaType())
            
            val request = Request.Builder()
                .url("$backendUrl/api/agents/register")
                .post(body)
                .build()
            
            try {
                client.newCall(request).execute().close()
                Log.d(TAG, "Agent registered successfully")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to register agent: ${e.message}")
            }
        }
    }
}

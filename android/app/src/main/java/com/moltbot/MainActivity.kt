package com.moltbot

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.moltbot.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.IOException

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val client = OkHttpClient()
    private val gson = Gson()
    private val messages = mutableListOf<ChatMessage>()
    private lateinit var adapter: ChatAdapter
    private lateinit var voiceRecorder: VoiceRecorder

    // Backend URL from BuildConfig
    private val backendUrl: String
        get() = BuildConfig.BACKEND_URL
    private var conversationId: String? = null

    // Permission launcher for RECORD_AUDIO
    private val requestMicPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) startVoiceInput()
            else Toast.makeText(this, "Microphone permission required for voice input", Toast.LENGTH_SHORT).show()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        voiceRecorder = VoiceRecorder(this)
        setupUI()
        checkAccessibilityService()
    }
    
    override fun onResume() {
        super.onResume()
        updateServiceStatus()
    }
    
    private fun setupUI() {
        // Setup RecyclerView
        adapter = ChatAdapter(messages)
        binding.messagesRecyclerView.apply {
            layoutManager = LinearLayoutManager(this@MainActivity).apply {
                stackFromEnd = true
            }
            adapter = this@MainActivity.adapter
        }
        
        // Setup send button
        binding.sendButton.setOnClickListener {
            val message = binding.messageInput.text.toString().trim()
            if (message.isNotEmpty()) {
                sendMessage(message)
                binding.messageInput.text?.clear()
            }
        }
        
        // Setup mic button
        binding.micButton.setOnClickListener {
            handleMicButton()
        }

        // Setup accessibility button
        binding.enableAccessibilityButton.setOnClickListener {
            openAccessibilitySettings()
        }
    }

    // ── Voice input ──────────────────────────────────────────────────────────

    private fun handleMicButton() {
        if (voiceRecorder.isRecording) {
            // Stop and transcribe
            binding.micButton.setImageResource(android.R.drawable.ic_btn_speak_now)
            binding.micButton.backgroundTintList =
                android.content.res.ColorStateList.valueOf(0xFF1A1A1A.toInt())
            lifecycleScope.launch {
                val text = voiceRecorder.stopAndTranscribe(backendUrl)
                withContext(Dispatchers.Main) {
                    if (!text.isNullOrBlank()) {
                        sendMessage(text)
                    } else {
                        Toast.makeText(this@MainActivity, "Could not transcribe audio", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        } else {
            // Request permission then start
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                == PackageManager.PERMISSION_GRANTED
            ) {
                startVoiceInput()
            } else {
                requestMicPermission.launch(Manifest.permission.RECORD_AUDIO)
            }
        }
    }

    private fun startVoiceInput() {
        val started = voiceRecorder.startRecording()
        if (started) {
            // Turn button red while recording
            binding.micButton.setImageResource(android.R.drawable.ic_media_pause)
            binding.micButton.backgroundTintList =
                android.content.res.ColorStateList.valueOf(0xCCF44336.toInt())
            Toast.makeText(this, "Listening… tap again to send", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "Could not start recording", Toast.LENGTH_SHORT).show()
        }
    }
    
    private fun checkAccessibilityService() {
        if (MoltBotAccessibilityService.isRunning) {
            binding.accessibilityCard.visibility = View.GONE
        } else {
            binding.accessibilityCard.visibility = View.VISIBLE
        }
    }
    
    private fun updateServiceStatus() {
        val isRunning = MoltBotAccessibilityService.isRunning
        binding.accessibilityCard.visibility = if (isRunning) View.GONE else View.VISIBLE
        binding.statusText.text = if (isRunning) "MoltBot is active \uD83D\uDFE2" else "Service not running"
    }
    
    private fun openAccessibilitySettings() {
        val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
        startActivity(intent)
        Toast.makeText(this, "Enable MoltBot in Accessibility settings", Toast.LENGTH_LONG).show()
    }
    
    private fun sendMessage(content: String) {
        // Add user message immediately
        messages.add(ChatMessage("user", content))
        adapter.notifyItemInserted(messages.size - 1)
        binding.messagesRecyclerView.scrollToPosition(messages.size - 1)
        
        // Show loading
        binding.loadingIndicator.visibility = View.VISIBLE
        
        lifecycleScope.launch {
            try {
                val response = sendChatRequest(content)
                withContext(Dispatchers.Main) {
                    binding.loadingIndicator.visibility = View.GONE
                    
                    if (response != null) {
                        val assistantContent = response["message"]?.let { 
                            (it as? Map<*, *>)?.get("content") as? String 
                        } ?: "No response"
                        
                        conversationId = response["conversation_id"] as? String
                        
                        messages.add(ChatMessage("assistant", assistantContent))
                        adapter.notifyItemInserted(messages.size - 1)
                        binding.messagesRecyclerView.scrollToPosition(messages.size - 1)
                    } else {
                        messages.add(ChatMessage("assistant", "Error: Could not get response"))
                        adapter.notifyItemInserted(messages.size - 1)
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    binding.loadingIndicator.visibility = View.GONE
                    messages.add(ChatMessage("assistant", "Error: ${e.message}"))
                    adapter.notifyItemInserted(messages.size - 1)
                }
            }
        }
    }
    
    private suspend fun sendChatRequest(content: String): Map<String, Any>? {
        return withContext(Dispatchers.IO) {
            val requestBody = mapOf(
                "content" to content,
                "conversation_id" to conversationId
            )
            
            val json = gson.toJson(requestBody)
            val body = json.toRequestBody("application/json".toMediaType())
            
            val request = Request.Builder()
                .url("$backendUrl/api/chat")
                .post(body)
                .build()
            
            try {
                client.newCall(request).execute().use { response ->
                    if (response.isSuccessful) {
                        val responseBody = response.body?.string()
                        val type = object : TypeToken<Map<String, Any>>() {}.type
                        gson.fromJson(responseBody, type)
                    } else {
                        null
                    }
                }
            } catch (e: IOException) {
                null
            }
        }
    }
}

data class ChatMessage(
    val role: String,
    val content: String
)

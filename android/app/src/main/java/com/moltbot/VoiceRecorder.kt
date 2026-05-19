package com.moltbot

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.MediaRecorder
import android.os.Build
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.asRequestBody
import org.json.JSONObject
import java.io.File
import java.io.IOException

/**
 * Handles microphone recording and transcription via /api/transcribe (Whisper).
 */
class VoiceRecorder(private val context: Context) {

    companion object {
        private const val TAG = "VoiceRecorder"
    }

    private var recorder: MediaRecorder? = null
    private var audioFile: File? = null
    private val httpClient = OkHttpClient()

    val isRecording: Boolean get() = recorder != null

    /** Returns true if RECORD_AUDIO permission is granted. */
    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                PackageManager.PERMISSION_GRANTED

    /** Start recording to a temp file. Returns false if no permission. */
    fun startRecording(): Boolean {
        if (!hasPermission()) return false
        cancel()  // clean up any leftover

        val file = File.createTempFile("moltbot_voice_", ".m4a", context.cacheDir)
        audioFile = file

        recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            @Suppress("DEPRECATION")
            MediaRecorder()
        }.apply {
            setAudioSource(MediaRecorder.AudioSource.MIC)
            setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
            setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
            setAudioSamplingRate(16000)
            setAudioEncodingBitRate(128000)
            setOutputFile(file.absolutePath)
            try {
                prepare()
                start()
                Log.d(TAG, "Recording started → ${file.name}")
            } catch (e: Exception) {
                Log.e(TAG, "Recorder prepare/start failed: ${e.message}")
                release()
                recorder = null
                return false
            }
        }
        return true
    }

    /**
     * Stop recording and POST the audio file to /api/transcribe.
     * Returns the transcribed text, or null on failure.
     */
    suspend fun stopAndTranscribe(backendUrl: String): String? = withContext(Dispatchers.IO) {
        try {
            recorder?.apply {
                stop()
                release()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Recorder stop error: ${e.message}")
        } finally {
            recorder = null
        }

        val file = audioFile ?: return@withContext null
        if (!file.exists() || file.length() == 0L) {
            Log.w(TAG, "Audio file empty or missing")
            return@withContext null
        }

        return@withContext try {
            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart(
                    "audio",
                    file.name,
                    file.asRequestBody("audio/m4a".toMediaType())
                )
                .build()

            val request = Request.Builder()
                .url("$backendUrl/api/transcribe")
                .post(requestBody)
                .build()

            httpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    Log.e(TAG, "Transcribe HTTP ${response.code}")
                    null
                } else {
                    val body = response.body?.string() ?: return@use null
                    val json = JSONObject(body)
                    val text = json.optString("text", "").trim()
                    Log.d(TAG, "Transcribed: $text")
                    text.ifEmpty { null }
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "Transcribe request failed: ${e.message}")
            null
        } finally {
            file.delete()
            audioFile = null
        }
    }

    /** Release resources without transcribing (e.g., on cancel). */
    fun cancel() {
        try {
            recorder?.apply { stop(); release() }
        } catch (_: Exception) {}
        recorder = null
        audioFile?.delete()
        audioFile = null
    }
}

package com.moltbot

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.AlarmClock
import android.provider.ContactsContract
import android.telephony.SmsManager
import android.util.Log
import java.util.Calendar

object PhoneActions {
    private const val TAG = "PhoneActions"
    
    fun setAlarm(context: Context, time: String, title: String): Map<String, Any> {
        return try {
            // Parse time (e.g., "7:00 AM", "14:30")
            val (hour, minute) = parseTime(time)
            
            val intent = Intent(AlarmClock.ACTION_SET_ALARM).apply {
                putExtra(AlarmClock.EXTRA_HOUR, hour)
                putExtra(AlarmClock.EXTRA_MINUTES, minute)
                putExtra(AlarmClock.EXTRA_MESSAGE, title)
                putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            
            context.startActivity(intent)
            mapOf("success" to true, "message" to "Alarm set for $hour:${minute.toString().padStart(2, '0')}")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to set alarm: ${e.message}")
            mapOf("success" to false, "message" to "Failed to set alarm: ${e.message}")
        }
    }
    
    private fun parseTime(time: String): Pair<Int, Int> {
        val cleanTime = time.trim().uppercase()
        val isPM = cleanTime.contains("PM")
        val isAM = cleanTime.contains("AM")
        
        val timePart = cleanTime.replace("AM", "").replace("PM", "").trim()
        val parts = timePart.split(":")
        
        var hour = parts[0].trim().toInt()
        val minute = if (parts.size > 1) parts[1].trim().toInt() else 0
        
        if (isPM && hour < 12) hour += 12
        if (isAM && hour == 12) hour = 0
        
        return Pair(hour, minute)
    }
    
    fun sendSMS(context: Context, phoneNumber: String, message: String): Map<String, Any> {
        return try {
            val intent = Intent(Intent.ACTION_SENDTO).apply {
                data = Uri.parse("smsto:$phoneNumber")
                putExtra("sms_body", message)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            mapOf("success" to true, "message" to "SMS composer opened for $phoneNumber")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send SMS: ${e.message}")
            mapOf("success" to false, "message" to "Failed to send SMS: ${e.message}")
        }
    }
    
    fun makeCall(context: Context, phoneNumber: String): Map<String, Any> {
        return try {
            val intent = Intent(Intent.ACTION_DIAL).apply {
                data = Uri.parse("tel:$phoneNumber")
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            mapOf("success" to true, "message" to "Dialer opened for $phoneNumber")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to make call: ${e.message}")
            mapOf("success" to false, "message" to "Failed to make call: ${e.message}")
        }
    }
    
    fun openApp(context: Context, packageName: String): Map<String, Any> {
        return try {
            val intent = context.packageManager.getLaunchIntentForPackage(packageName)
            if (intent != null) {
                intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                context.startActivity(intent)
                mapOf("success" to true, "message" to "Opening $packageName")
            } else {
                mapOf("success" to false, "message" to "App not found: $packageName")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to open app: ${e.message}")
            mapOf("success" to false, "message" to "Failed to open app: ${e.message}")
        }
    }
    
    fun searchContacts(context: Context, query: String): Map<String, Any> {
        return try {
            val contacts = mutableListOf<Map<String, String?>>()
            val cursor = context.contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                arrayOf(
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                ),
                "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} LIKE ?",
                arrayOf("%$query%"),
                null
            )
            
            cursor?.use {
                while (it.moveToNext()) {
                    contacts.add(mapOf(
                        "name" to it.getString(0),
                        "phone" to it.getString(1)
                    ))
                }
            }
            
            mapOf(
                "success" to true,
                "message" to "Found ${contacts.size} contacts",
                "data" to contacts
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to search contacts: ${e.message}")
            mapOf("success" to false, "message" to "Failed to search contacts: ${e.message}")
        }
    }
}

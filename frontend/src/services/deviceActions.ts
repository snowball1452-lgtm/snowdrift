import { Platform, Linking, Alert } from 'react-native';
import * as Calendar from 'expo-calendar';
import * as Contacts from 'expo-contacts';
import * as SMS from 'expo-sms';
import * as Clipboard from 'expo-clipboard';

// Note: expo-notifications removed from Expo Go in SDK 53
// Using local notifications via expo-calendar alarms instead

export interface DeviceAction {
  action: string;
  params: Record<string, any>;
}

export interface DeviceActionResult {
  success: boolean;
  message: string;
  data?: any;
}

class DeviceActionsManager {
  private calendarId: string | null = null;

  // ==================== PERMISSIONS ====================
  
  async requestCalendarPermissions(): Promise<boolean> {
    try {
      const { status } = await Calendar.requestCalendarPermissionsAsync();
      return status === 'granted';
    } catch (e) {
      console.log('Calendar permission error:', e);
      return false;
    }
  }

  async requestContactsPermissions(): Promise<boolean> {
    try {
      const { status } = await Contacts.requestPermissionsAsync();
      return status === 'granted';
    } catch (e) {
      console.log('Contacts permission error:', e);
      return false;
    }
  }

  // ==================== CALENDAR / ALARMS ====================

  private async getOrCreateCalendar(): Promise<string> {
    if (this.calendarId) return this.calendarId;

    const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
    
    // Find default calendar
    const defaultCalendar = calendars.find(
      cal => cal.allowsModifications && cal.source?.name === 'Default'
    ) || calendars.find(cal => cal.allowsModifications);

    if (defaultCalendar) {
      this.calendarId = defaultCalendar.id;
      return defaultCalendar.id;
    }

    // Create a new calendar if needed (Android only)
    if (Platform.OS === 'android') {
      const newCalendarId = await Calendar.createCalendarAsync({
        title: 'SnowDrift',
        color: '#ff6b35',
        entityType: Calendar.EntityTypes.EVENT,
        source: {
          isLocalAccount: true,
          name: 'SnowDrift',
          type: Calendar.SourceType.LOCAL,
        },
        name: 'SnowDrift Calendar',
        ownerAccount: 'snowdrift',
        accessLevel: Calendar.CalendarAccessLevel.OWNER,
      });
      this.calendarId = newCalendarId;
      return newCalendarId;
    }

    throw new Error('No writable calendar found');
  }

  async setAlarm(time: string, title: string = 'SnowDrift Alarm'): Promise<DeviceActionResult> {
    try {
      const hasPermission = await this.requestCalendarPermissions();
      if (!hasPermission) {
        return { success: false, message: 'Calendar permission denied. Please grant calendar access.' };
      }

      // Parse time (expects "HH:MM" or "HH:MM AM/PM")
      const now = new Date();
      let [hours, minutes] = time.replace(/[AP]M/i, '').trim().split(':').map(Number);
      
      if (time.toLowerCase().includes('pm') && hours < 12) hours += 12;
      if (time.toLowerCase().includes('am') && hours === 12) hours = 0;

      const alarmDate = new Date(now);
      alarmDate.setHours(hours, minutes, 0, 0);
      
      // If time has passed today, set for tomorrow
      if (alarmDate <= now) {
        alarmDate.setDate(alarmDate.getDate() + 1);
      }

      const calendarId = await this.getOrCreateCalendar();
      
      const eventId = await Calendar.createEventAsync(calendarId, {
        title: title,
        startDate: alarmDate,
        endDate: new Date(alarmDate.getTime() + 30 * 60000), // 30 min duration
        alarms: [{ relativeOffset: 0 }], // Alert at event time
        notes: 'Created by SnowDrift',
      });

      return {
        success: true,
        message: `Alarm set for ${alarmDate.toLocaleTimeString()}`,
        data: { eventId, time: alarmDate.toISOString() }
      };
    } catch (error: any) {
      return { success: false, message: `Failed to set alarm: ${error.message}` };
    }
  }

  async createReminder(title: string, datetime: Date, notes?: string): Promise<DeviceActionResult> {
    try {
      const hasPermission = await this.requestCalendarPermissions();
      if (!hasPermission) {
        return { success: false, message: 'Calendar permission denied' };
      }

      const calendarId = await this.getOrCreateCalendar();
      
      const eventId = await Calendar.createEventAsync(calendarId, {
        title,
        startDate: datetime,
        endDate: new Date(datetime.getTime() + 15 * 60000),
        alarms: [{ relativeOffset: -5 }], // 5 min before
        notes: notes || 'Created by SnowDrift',
      });

      return {
        success: true,
        message: `Reminder set for ${datetime.toLocaleString()}`,
        data: { eventId }
      };
    } catch (error: any) {
      return { success: false, message: `Failed to create reminder: ${error.message}` };
    }
  }

  // ==================== SMS / CALLS ====================

  async sendSMS(phoneNumber: string, message: string): Promise<DeviceActionResult> {
    try {
      const isAvailable = await SMS.isAvailableAsync();
      if (!isAvailable) {
        return { success: false, message: 'SMS is not available on this device' };
      }

      const { result } = await SMS.sendSMSAsync([phoneNumber], message);
      
      return {
        success: result === 'sent' || result === 'unknown',
        message: result === 'sent' ? 'SMS sent' : `SMS result: ${result}`,
      };
    } catch (error: any) {
      return { success: false, message: `Failed to send SMS: ${error.message}` };
    }
  }

  async makeCall(phoneNumber: string): Promise<DeviceActionResult> {
    try {
      const url = `tel:${phoneNumber}`;
      const canOpen = await Linking.canOpenURL(url);
      
      if (!canOpen) {
        return { success: false, message: 'Cannot make calls on this device' };
      }

      await Linking.openURL(url);
      return { success: true, message: `Calling ${phoneNumber}` };
    } catch (error: any) {
      return { success: false, message: `Failed to make call: ${error.message}` };
    }
  }

  // ==================== CONTACTS ====================

  async searchContacts(query: string): Promise<DeviceActionResult> {
    try {
      const hasPermission = await this.requestContactsPermissions();
      if (!hasPermission) {
        return { success: false, message: 'Contacts permission denied' };
      }

      const { data } = await Contacts.getContactsAsync({
        fields: [Contacts.Fields.Name, Contacts.Fields.PhoneNumbers, Contacts.Fields.Emails],
      });

      const matches = data.filter(contact => 
        contact.name?.toLowerCase().includes(query.toLowerCase())
      ).slice(0, 10);

      return {
        success: true,
        message: `Found ${matches.length} contacts`,
        data: matches.map(c => ({
          name: c.name,
          phone: c.phoneNumbers?.[0]?.number,
          email: c.emails?.[0]?.email,
        }))
      };
    } catch (error: any) {
      return { success: false, message: `Failed to search contacts: ${error.message}` };
    }
  }

  // ==================== APP LAUNCHING ====================

  async openApp(appName: string): Promise<DeviceActionResult> {
    try {
      // Common app URL schemes
      const schemes: Record<string, string> = {
        'spotify': 'spotify://',
        'twitter': 'twitter://',
        'x': 'twitter://',
        'instagram': 'instagram://',
        'whatsapp': 'whatsapp://',
        'telegram': 'telegram://',
        'slack': 'slack://',
        'maps': Platform.OS === 'ios' ? 'maps://' : 'geo:',
        'music': 'music://',
        'photos': 'photos-redirect://',
        'settings': Platform.OS === 'ios' ? 'App-Prefs://' : 'android.settings.SETTINGS',
        'mail': 'mailto:',
        'youtube': 'youtube://',
        'netflix': 'nflx://',
        'facebook': 'fb://',
        'messenger': 'fb-messenger://',
        'chrome': 'googlechrome://',
        'safari': 'http://',
      };

      const appLower = appName.toLowerCase();
      const scheme = schemes[appLower] || `${appLower}://`;
      
      const canOpen = await Linking.canOpenURL(scheme);
      
      if (canOpen) {
        await Linking.openURL(scheme);
        return { success: true, message: `Opening ${appName}` };
      } else {
        // Try app store as fallback
        return { success: false, message: `Cannot open ${appName}. App may not be installed.` };
      }
    } catch (error: any) {
      return { success: false, message: `Failed to open app: ${error.message}` };
    }
  }

  async openURL(url: string): Promise<DeviceActionResult> {
    try {
      const canOpen = await Linking.canOpenURL(url);
      if (!canOpen) {
        return { success: false, message: `Cannot open URL: ${url}` };
      }
      await Linking.openURL(url);
      return { success: true, message: `Opening ${url}` };
    } catch (error: any) {
      return { success: false, message: `Failed to open URL: ${error.message}` };
    }
  }

  // ==================== CLIPBOARD ====================

  async copyToClipboard(text: string): Promise<DeviceActionResult> {
    try {
      await Clipboard.setStringAsync(text);
      return { success: true, message: 'Copied to clipboard' };
    } catch (error: any) {
      return { success: false, message: `Failed to copy: ${error.message}` };
    }
  }

  async getClipboard(): Promise<DeviceActionResult> {
    try {
      const text = await Clipboard.getStringAsync();
      return { success: true, message: 'Clipboard content retrieved', data: text };
    } catch (error: any) {
      return { success: false, message: `Failed to get clipboard: ${error.message}` };
    }
  }

  // ==================== ACTION DISPATCHER ====================

  async executeAction(action: DeviceAction): Promise<DeviceActionResult> {
    const { action: actionType, params } = action;

    try {
      switch (actionType) {
        case 'set_alarm':
          return await this.setAlarm(params.time, params.title);
        
        case 'create_reminder':
          return await this.createReminder(params.title, new Date(params.datetime), params.notes);
        
        case 'send_sms':
          return await this.sendSMS(params.phone, params.message);
        
        case 'make_call':
          return await this.makeCall(params.phone);
        
        case 'search_contacts':
          return await this.searchContacts(params.query);
        
        case 'open_app':
          return await this.openApp(params.app);
        
        case 'open_url':
          return await this.openURL(params.url);
        
        case 'copy_clipboard':
          return await this.copyToClipboard(params.text);
        
        case 'get_clipboard':
          return await this.getClipboard();
        
        default:
          return { success: false, message: `Unknown device action: ${actionType}` };
      }
    } catch (error: any) {
      return { success: false, message: `Action failed: ${error.message}` };
    }
  }
}

export const deviceActions = new DeviceActionsManager();

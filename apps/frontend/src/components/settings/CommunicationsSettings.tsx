/**
 * Kaison K1 - Communications Settings Component
 * Configure notification channels (Email, Slack, Webhooks)
 * Integrates with NotificationService backend API
 */

import React, { useState, useEffect } from 'react';
import { COLORS, UI, BRANDING } from '@/theme/branding';
import './CommunicationsSettings.css';

interface EmailProvider {
  type: 'gmail' | 'protonmail' | 'smtp';
  configured: boolean;
  address?: string;
}

interface NotificationChannel {
  email: boolean;
  slack: boolean;
  webhook: boolean;
}

interface NotificationRules {
  finding_min_cvss: number;
  finding_recipients: string[];
  daily_summary: boolean;
  weekly_statistics: boolean;
  approval_notifications: boolean;
}

interface SlackConfig {
  webhook_url: string;
  channel: string;
}

interface WebhookConfig {
  url: string;
  secret: string;
  events: string[];
}

const CommunicationsSettings: React.FC = () => {
  // State management
  const [emailProviders, setEmailProviders] = useState<EmailProvider[]>([]);
  const [activeProvider, setActiveProvider] = useState<EmailProvider | null>(null);
  const [channels, setChannels] = useState<NotificationChannel>({
    email: false,
    slack: false,
    webhook: false,
  });
  const [rules, setRules] = useState<NotificationRules>({
    finding_min_cvss: 7.0,
    finding_recipients: [],
    daily_summary: true,
    weekly_statistics: true,
    approval_notifications: true,
  });
  const [slackConfig, setSlackConfig] = useState<SlackConfig>({
    webhook_url: '',
    channel: '#security-alerts',
  });
  const [webhookConfig, setWebhookConfig] = useState<WebhookConfig>({
    url: '',
    secret: '',
    events: ['finding', 'approval_request', 'scan_complete'],
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Email setup state
  const [gmailAuthUrl, setGmailAuthUrl] = useState('');
  const [protonConfig, setProtonConfig] = useState({ user: '', password: '' });
  const [smtpConfig, setSmtpConfig] = useState({
    host: '',
    port: 587,
    user: '',
    password: '',
    from_email: '',
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      // Fetch email providers
      const providersRes = await fetch('/api/v1/notifications/providers');
      const providersData = await providersRes.json();

      if (providersData.success) {
        setEmailProviders(providersData.data.providers || []);
        setActiveProvider(providersData.data.active_provider || null);
      }

      // Fetch notification rules
      const rulesRes = await fetch('/api/v1/notifications/rules');
      const rulesData = await rulesRes.json();

      if (rulesData.success) {
        setRules(rulesData.data || rules);
      }

      // Fetch Slack config
      const slackRes = await fetch('/api/v1/notifications/slack/config');
      const slackData = await slackRes.json();

      if (slackData.success && slackData.data) {
        setSlackConfig(slackData.data);
        setChannels(prev => ({ ...prev, slack: true }));
      }

      // Fetch Webhook config
      const webhookRes = await fetch('/api/v1/notifications/webhook/config');
      const webhookData = await webhookRes.json();

      if (webhookData.success && webhookData.data) {
        setWebhookConfig(webhookData.data);
        setChannels(prev => ({ ...prev, webhook: true }));
      }

      setLoading(false);
    } catch (error) {
      console.error('Error fetching settings:', error);
      setMessage({ type: 'error', text: 'Failed to load settings' });
      setLoading(false);
    }
  };

  const handleGmailAuth = async () => {
    try {
      const res = await fetch('/api/v1/notifications/gmail/auth', { method: 'POST' });
      const data = await res.json();

      if (data.success) {
        setGmailAuthUrl(data.data.authorization_url);
        window.open(data.data.authorization_url, '_blank');
        setMessage({ type: 'success', text: 'Gmail authorization started. Complete in new window.' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Gmail authorization failed' });
    }
  };

  const handleProtonmailSetup = async () => {
    try {
      setSaving(true);
      const res = await fetch('/api/v1/notifications/protonmail/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bridge_user: protonConfig.user,
          bridge_password: protonConfig.password,
        }),
      });

      const data = await res.json();

      if (data.success) {
        setMessage({ type: 'success', text: 'ProtonMail configured successfully' });
        fetchSettings();
      } else {
        setMessage({ type: 'error', text: data.message || 'ProtonMail setup failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'ProtonMail setup failed' });
    } finally {
      setSaving(false);
    }
  };

  const handleSMTPSetup = async () => {
    try {
      setSaving(true);
      const res = await fetch('/api/v1/notifications/smtp/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(smtpConfig),
      });

      const data = await res.json();

      if (data.success) {
        setMessage({ type: 'success', text: 'SMTP configured successfully' });
        fetchSettings();
      } else {
        setMessage({ type: 'error', text: data.message || 'SMTP setup failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'SMTP setup failed' });
    } finally {
      setSaving(false);
    }
  };

  const handleSlackSetup = async () => {
    try {
      setSaving(true);
      const res = await fetch('/api/v1/notifications/slack/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(slackConfig),
      });

      const data = await res.json();

      if (data.success) {
        setMessage({ type: 'success', text: 'Slack configured successfully' });
        setChannels(prev => ({ ...prev, slack: true }));
      } else {
        setMessage({ type: 'error', text: data.message || 'Slack setup failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Slack setup failed' });
    } finally {
      setSaving(false);
    }
  };

  const handleWebhookSetup = async () => {
    try {
      setSaving(true);
      const res = await fetch('/api/v1/notifications/webhook/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(webhookConfig),
      });

      const data = await res.json();

      if (data.success) {
        setMessage({ type: 'success', text: 'Webhook configured successfully' });
        setChannels(prev => ({ ...prev, webhook: true }));
      } else {
        setMessage({ type: 'error', text: data.message || 'Webhook setup failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Webhook setup failed' });
    } finally {
      setSaving(false);
    }
  };

  const handleRulesUpdate = async () => {
    try {
      setSaving(true);
      const res = await fetch('/api/v1/notifications/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rules),
      });

      const data = await res.json();

      if (data.success) {
        setMessage({ type: 'success', text: 'Notification rules updated' });
      } else {
        setMessage({ type: 'error', text: data.message || 'Rules update failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Rules update failed' });
    } finally {
      setSaving(false);
    }
  };

  const sendTestNotification = async () => {
    if (!activeProvider) {
      setMessage({ type: 'error', text: 'No email provider configured' });
      return;
    }

    try {
      setSaving(true);
      const res = await fetch('/api/v1/notifications/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: activeProvider.address,
          subject: `Kaison K1 Test Notification`,
          body: 'This is a test notification from Kaison K1 Platform',
        }),
      });

      const data = await res.json();

      if (data.success) {
        setMessage({ type: 'success', text: 'Test notification sent successfully' });
      } else {
        setMessage({ type: 'error', text: data.message || 'Test failed' });
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Test notification failed' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="settings-loading">
        <div className="spinner"></div>
        <p>Loading settings...</p>
      </div>
    );
  }

  return (
    <div className="communications-settings" style={{
      backgroundColor: COLORS.background,
      color: COLORS.text
    }}>
      <div className="settings-header">
        <h1 style={{ color: COLORS.primary.main }}>Communications Settings</h1>
        <p style={{ color: COLORS.textSecondary }}>
          Configure notification channels for findings, approvals, and reports
        </p>
      </div>

      {message && (
        <div
          className={`message message-${message.type}`}
          style={{
            backgroundColor: message.type === 'success'
              ? COLORS.status.success + '20'
              : COLORS.status.error + '20',
            borderLeft: `4px solid ${message.type === 'success' ? COLORS.status.success : COLORS.status.error}`,
            color: COLORS.text,
          }}
        >
          {message.text}
          <button onClick={() => setMessage(null)} style={{ color: COLORS.text }}>✕</button>
        </div>
      )}

      {/* Email Provider Configuration */}
      <section className="settings-section">
        <h2 style={{ color: COLORS.primary.main }}>Email Provider</h2>

        <div className="provider-status">
          {activeProvider ? (
            <div className="active-provider" style={{
              backgroundColor: COLORS.surface,
              borderLeft: `4px solid ${COLORS.status.success}`
            }}>
              <span className="provider-badge" style={{ color: COLORS.status.success }}>✓ Active</span>
              <p>{activeProvider.type.toUpperCase()}: {activeProvider.address}</p>
            </div>
          ) : (
            <div className="no-provider" style={{
              backgroundColor: COLORS.surface,
              borderLeft: `4px solid ${COLORS.status.warning}`
            }}>
              <span className="provider-badge" style={{ color: COLORS.status.warning }}>⚠ Not Configured</span>
              <p>No email provider configured</p>
            </div>
          )}
        </div>

        <div className="provider-options">
          {/* Gmail OAuth */}
          <div className="provider-card" style={{ backgroundColor: COLORS.surface }}>
            <h3>Gmail (OAuth)</h3>
            <p style={{ color: COLORS.textSecondary }}>Recommended for personal use</p>
            <button
              onClick={handleGmailAuth}
              className="btn-primary"
              style={{
                backgroundColor: COLORS.primary.main,
                color: COLORS.text
              }}
            >
              Authorize Gmail
            </button>
          </div>

          {/* ProtonMail Bridge */}
          <div className="provider-card" style={{ backgroundColor: COLORS.surface }}>
            <h3>ProtonMail Bridge</h3>
            <p style={{ color: COLORS.textSecondary }}>Secure, encrypted email</p>
            <input
              type="email"
              placeholder="Bridge Username"
              value={protonConfig.user}
              onChange={(e) => setProtonConfig({ ...protonConfig, user: e.target.value })}
              style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
            />
            <input
              type="password"
              placeholder="Bridge Password"
              value={protonConfig.password}
              onChange={(e) => setProtonConfig({ ...protonConfig, password: e.target.value })}
              style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
            />
            <button
              onClick={handleProtonmailSetup}
              disabled={saving}
              className="btn-primary"
              style={{
                backgroundColor: COLORS.primary.main,
                color: COLORS.text
              }}
            >
              {saving ? 'Connecting...' : 'Connect ProtonMail'}
            </button>
          </div>

          {/* SMTP Custom */}
          <div className="provider-card" style={{ backgroundColor: COLORS.surface }}>
            <h3>Custom SMTP</h3>
            <p style={{ color: COLORS.textSecondary }}>Any SMTP server</p>
            <input
              type="text"
              placeholder="SMTP Host"
              value={smtpConfig.host}
              onChange={(e) => setSmtpConfig({ ...smtpConfig, host: e.target.value })}
              style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
            />
            <input
              type="number"
              placeholder="Port"
              value={smtpConfig.port}
              onChange={(e) => setSmtpConfig({ ...smtpConfig, port: parseInt(e.target.value) })}
              style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
            />
            <input
              type="text"
              placeholder="Username"
              value={smtpConfig.user}
              onChange={(e) => setSmtpConfig({ ...smtpConfig, user: e.target.value })}
              style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
            />
            <input
              type="password"
              placeholder="Password"
              value={smtpConfig.password}
              onChange={(e) => setSmtpConfig({ ...smtpConfig, password: e.target.value })}
              style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
            />
            <input
              type="email"
              placeholder="From Email"
              value={smtpConfig.from_email}
              onChange={(e) => setSmtpConfig({ ...smtpConfig, from_email: e.target.value })}
              style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
            />
            <button
              onClick={handleSMTPSetup}
              disabled={saving}
              className="btn-primary"
              style={{
                backgroundColor: COLORS.primary.main,
                color: COLORS.text
              }}
            >
              {saving ? 'Connecting...' : 'Connect SMTP'}
            </button>
          </div>
        </div>

        {activeProvider && (
          <button
            onClick={sendTestNotification}
            className="btn-secondary"
            disabled={saving}
            style={{
              backgroundColor: COLORS.secondary.main,
              color: COLORS.text
            }}
          >
            {saving ? 'Sending...' : 'Send Test Email'}
          </button>
        )}
      </section>

      {/* Slack Integration */}
      <section className="settings-section">
        <h2 style={{ color: COLORS.primary.main }}>Slack Integration</h2>

        <div className="slack-config">
          <input
            type="url"
            placeholder="Slack Webhook URL"
            value={slackConfig.webhook_url}
            onChange={(e) => setSlackConfig({ ...slackConfig, webhook_url: e.target.value })}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          />
          <input
            type="text"
            placeholder="Channel (e.g., #security)"
            value={slackConfig.channel}
            onChange={(e) => setSlackConfig({ ...slackConfig, channel: e.target.value })}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          />
          <button
            onClick={handleSlackSetup}
            disabled={saving}
            className="btn-primary"
            style={{
              backgroundColor: COLORS.primary.main,
              color: COLORS.text
            }}
          >
            {saving ? 'Saving...' : 'Save Slack Config'}
          </button>
        </div>
      </section>

      {/* Webhook Integration */}
      <section className="settings-section">
        <h2 style={{ color: COLORS.primary.main }}>Webhook Integration</h2>

        <div className="webhook-config">
          <input
            type="url"
            placeholder="Webhook URL"
            value={webhookConfig.url}
            onChange={(e) => setWebhookConfig({ ...webhookConfig, url: e.target.value })}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          />
          <input
            type="text"
            placeholder="Secret (optional)"
            value={webhookConfig.secret}
            onChange={(e) => setWebhookConfig({ ...webhookConfig, secret: e.target.value })}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          />
          <div className="webhook-events">
            <label style={{ color: COLORS.text }}>Events to send:</label>
            {['finding', 'approval_request', 'scan_complete', 'error'].map(event => (
              <label key={event} className="checkbox-label" style={{ color: COLORS.text }}>
                <input
                  type="checkbox"
                  checked={webhookConfig.events.includes(event)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setWebhookConfig({
                        ...webhookConfig,
                        events: [...webhookConfig.events, event]
                      });
                    } else {
                      setWebhookConfig({
                        ...webhookConfig,
                        events: webhookConfig.events.filter(ev => ev !== event)
                      });
                    }
                  }}
                />
                {event.replace('_', ' ')}
              </label>
            ))}
          </div>
          <button
            onClick={handleWebhookSetup}
            disabled={saving}
            className="btn-primary"
            style={{
              backgroundColor: COLORS.primary.main,
              color: COLORS.text
            }}
          >
            {saving ? 'Saving...' : 'Save Webhook Config'}
          </button>
        </div>
      </section>

      {/* Notification Rules */}
      <section className="settings-section">
        <h2 style={{ color: COLORS.primary.main }}>Notification Rules</h2>

        <div className="rules-config">
          <div className="rule-item">
            <label style={{ color: COLORS.text }}>
              Minimum CVSS Score for Alerts: <strong>{rules.finding_min_cvss}</strong>
            </label>
            <input
              type="range"
              min="0"
              max="10"
              step="0.1"
              value={rules.finding_min_cvss}
              onChange={(e) => setRules({ ...rules, finding_min_cvss: parseFloat(e.target.value) })}
              style={{ accentColor: COLORS.primary.main }}
            />
          </div>

          <div className="rule-item">
            <label className="checkbox-label" style={{ color: COLORS.text }}>
              <input
                type="checkbox"
                checked={rules.daily_summary}
                onChange={(e) => setRules({ ...rules, daily_summary: e.target.checked })}
              />
              Daily Summary Report
            </label>
          </div>

          <div className="rule-item">
            <label className="checkbox-label" style={{ color: COLORS.text }}>
              <input
                type="checkbox"
                checked={rules.weekly_statistics}
                onChange={(e) => setRules({ ...rules, weekly_statistics: e.target.checked })}
              />
              Weekly Statistics Report
            </label>
          </div>

          <div className="rule-item">
            <label className="checkbox-label" style={{ color: COLORS.text }}>
              <input
                type="checkbox"
                checked={rules.approval_notifications}
                onChange={(e) => setRules({ ...rules, approval_notifications: e.target.checked })}
              />
              Agent Approval Request Notifications
            </label>
          </div>

          <button
            onClick={handleRulesUpdate}
            disabled={saving}
            className="btn-primary"
            style={{
              backgroundColor: COLORS.primary.main,
              color: COLORS.text
            }}
          >
            {saving ? 'Saving...' : 'Save Rules'}
          </button>
        </div>
      </section>
    </div>
  );
};

export default CommunicationsSettings;

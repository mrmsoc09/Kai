"""Form component for adding/updating credentials."""
import React, { useState } from 'react';
import styles from '../styles/credentials.module.css';

interface CredentialFormProps {
  accessType: string;
  onSubmit: (formData: any) => Promise<void>;
  onCancel: () => void;
  isLoading: boolean;
}

interface FormData {
  username?: string;
  password?: string;
  email?: string;
  api_key?: string;
  api_secret?: string;
  notes?: string;
  credentials: any;
}

interface FormErrors {
  [key: string]: string;
}

export default function CredentialForm({
  accessType,
  onSubmit,
  onCancel,
  isLoading,
}: CredentialFormProps) {
  const [formData, setFormData] = useState<FormData>({
    username: '',
    password: '',
    email: '',
    api_key: '',
    api_secret: '',
    notes: '',
    credentials: {},
  });

  const [errors, setErrors] = useState<FormErrors>({});

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (accessType === 'user_account') {
      if (!formData.username) newErrors.username = 'Username required';
      if (!formData.password) newErrors.password = 'Password required';
      if (!formData.email) newErrors.email = 'Email required';
      if (formData.password && formData.password.length < 8) {
        newErrors.password = 'Password must be at least 8 characters';
      }
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (formData.email && !emailRegex.test(formData.email)) {
        newErrors.email = 'Invalid email format';
      }
    }

    if (accessType === 'api_key') {
      if (!formData.api_key) newErrors.api_key = 'API key required';
      if (!formData.api_secret) newErrors.api_secret = 'API secret required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: '',
      }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    const submitData = {
      username: formData.username || formData.api_key,
      notes: formData.notes,
      credentials: {
        username: formData.username,
        password: formData.password,
        email: formData.email,
        api_key: formData.api_key,
        api_secret: formData.api_secret,
      },
    };

    try {
      await onSubmit(submitData);
    } catch (err) {
      // Error handling is done at parent level
      console.error('Form submission error:', err);
    }
  };

  return (
    <form onSubmit={handleSubmit} className={styles.form}>
      {accessType === 'user_account' && (
        <>
          <div className={styles.formGroup}>
            <label htmlFor="email">Email Address *</label>
            <input
              id="email"
              type="email"
              name="email"
              placeholder="test@example.com"
              value={formData.email}
              onChange={handleInputChange}
              disabled={isLoading}
            />
            {errors.email && <span className={styles.error}>{errors.email}</span>}
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="username">Username *</label>
            <input
              id="username"
              type="text"
              name="username"
              placeholder="username or email"
              value={formData.username}
              onChange={handleInputChange}
              disabled={isLoading}
            />
            {errors.username && <span className={styles.error}>{errors.username}</span>}
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="password">Password *</label>
            <input
              id="password"
              type="password"
              name="password"
              placeholder="Minimum 8 characters"
              value={formData.password}
              onChange={handleInputChange}
              disabled={isLoading}
              autoComplete="new-password"
            />
            {errors.password && <span className={styles.error}>{errors.password}</span>}
            <small>Password is encrypted and stored securely in Vault. Never logged.</small>
          </div>
        </>
      )}

      {accessType === 'api_key' && (
        <>
          <div className={styles.formGroup}>
            <label htmlFor="api_key">API Key *</label>
            <input
              id="api_key"
              type="password"
              name="api_key"
              placeholder="Your API key"
              value={formData.api_key}
              onChange={handleInputChange}
              disabled={isLoading}
              autoComplete="off"
            />
            {errors.api_key && <span className={styles.error}>{errors.api_key}</span>}
            <small>API key is encrypted and stored securely in Vault. Never logged.</small>
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="api_secret">API Secret *</label>
            <input
              id="api_secret"
              type="password"
              name="api_secret"
              placeholder="Your API secret"
              value={formData.api_secret}
              onChange={handleInputChange}
              disabled={isLoading}
              autoComplete="off"
            />
            {errors.api_secret && <span className={styles.error}>{errors.api_secret}</span>}
            <small>API secret is encrypted and stored securely in Vault. Never logged.</small>
          </div>
        </>
      )}

      {accessType === 'hunter_account' && (
        <>
          <div className={styles.formGroup}>
            <label htmlFor="username">Hunter ID *</label>
            <input
              id="username"
              type="text"
              name="username"
              placeholder="Your hunter ID"
              value={formData.username}
              onChange={handleInputChange}
              disabled={isLoading}
            />
            {errors.username && <span className={styles.error}>{errors.username}</span>}
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="api_key">API Token *</label>
            <input
              id="api_key"
              type="password"
              name="api_key"
              placeholder="Your API token"
              value={formData.api_key}
              onChange={handleInputChange}
              disabled={isLoading}
              autoComplete="off"
            />
            {errors.api_key && <span className={styles.error}>{errors.api_key}</span>}
            <small>API token is encrypted and stored securely in Vault. Never logged.</small>
          </div>
        </>
      )}

      <div className={styles.formGroup}>
        <label htmlFor="notes">Notes (Optional)</label>
        <textarea
          id="notes"
          name="notes"
          placeholder="e.g., Main testing account, API key for automated scanning"
          value={formData.notes}
          onChange={handleInputChange}
          disabled={isLoading}
          rows={3}
        />
      </div>

      <div className={styles.formActions}>
        <button
          type="submit"
          disabled={isLoading}
          className={styles.primaryButton}
        >
          {isLoading ? 'Saving...' : 'Save Credential'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isLoading}
          className={styles.secondaryButton}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

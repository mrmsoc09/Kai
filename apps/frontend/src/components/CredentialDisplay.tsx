"""Component for securely displaying credentials with masking."""
import React from 'react';
import styles from '../styles/credentials.module.css';

interface CredentialDisplayProps {
  credential: any;
  accessType: string;
}

export default function CredentialDisplay({
  credential,
  accessType,
}: CredentialDisplayProps) {
  const maskApiKey = (key?: string): string => {
    if (!key) return 'Not available';
    if (key.length <= 10) return '*'.repeat(key.length);
    return `${key.substring(0, 6)}***...${key.substring(key.length - 4)}`;
  };

  const maskPassword = (): string => {
    return '••••••••';
  };

  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'active':
        return '✓';
      case 'invalid':
        return '✗';
      case 'expired':
        return '⚠';
      case 'needs_renewal':
        return '⚠';
      default:
        return '?';
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'active':
        return 'success';
      case 'invalid':
        return 'error';
      case 'expired':
      case 'needs_renewal':
        return 'warning';
      default:
        return 'default';
    }
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'Never';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return 'Invalid date';
    }
  };

  return (
    <div className={styles.credentialDisplay}>
      {/* Status Badge */}
      <div className={`${styles.statusBadge} ${styles[getStatusColor(credential.status)]}`}>
        {getStatusIcon(credential.status)} {credential.status.toUpperCase()}
      </div>

      {/* User Account Display */}
      {accessType === 'user_account' && (
        <>
          <div className={styles.credentialField}>
            <span className={styles.label}>Username/Email:</span>
            <span className={styles.value}>
              {credential.credential_username || credential.credential_email || 'Not set'}
            </span>
          </div>

          <div className={styles.credentialField}>
            <span className={styles.label}>Password:</span>
            <span className={styles.value + ' ' + styles.masked}>{maskPassword()}</span>
          </div>

          <div className={styles.credentialField}>
            <span className={styles.label}>Email:</span>
            <span className={styles.value}>
              {credential.credential_email || 'Not set'}
            </span>
          </div>
        </>
      )}

      {/* API Key Display */}
      {accessType === 'api_key' && (
        <>
          <div className={styles.credentialField}>
            <span className={styles.label}>API Key:</span>
            <span className={styles.value + ' ' + styles.masked}>
              {maskApiKey(credential.credential_identifier)}
            </span>
          </div>

          <div className={styles.credentialField}>
            <span className={styles.label}>Secret:</span>
            <span className={styles.value + ' ' + styles.masked}>{maskPassword()}</span>
          </div>
        </>
      )}

      {/* Hunter Account Display */}
      {accessType === 'hunter_account' && (
        <>
          <div className={styles.credentialField}>
            <span className={styles.label}>Hunter ID:</span>
            <span className={styles.value}>
              {credential.credential_identifier || 'Not set'}
            </span>
          </div>

          <div className={styles.credentialField}>
            <span className={styles.label}>API Token:</span>
            <span className={styles.value + ' ' + styles.masked}>{maskPassword()}</span>
          </div>
        </>
      )}

      {/* Common Fields */}
      <div className={styles.credentialField}>
        <span className={styles.label}>Last Validated:</span>
        <span className={styles.value}>
          {credential.last_validated_at ? formatDate(credential.last_validated_at) : 'Never'}
        </span>
      </div>

      {credential.validation_success !== undefined && (
        <div className={styles.credentialField}>
          <span className={styles.label}>Validation Status:</span>
          <span className={styles.value}>
            {credential.validation_success ? '✓ Valid' : '✗ Failed'}
          </span>
        </div>
      )}

      <div className={styles.credentialField}>
        <span className={styles.label}>Access Count:</span>
        <span className={styles.value}>{credential.access_count || 0}</span>
      </div>

      {credential.notes && (
        <div className={styles.credentialField}>
          <span className={styles.label}>Notes:</span>
          <span className={styles.value}>{credential.notes}</span>
        </div>
      )}

      <div className={styles.securityNote}>
        ⚠️ Full credentials are never displayed. Passwords and API keys are stored encrypted in Vault.
      </div>
    </div>
  );
}

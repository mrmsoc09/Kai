"""React component for Credentials & Access Management tab."""
import React, { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { credentialsApi } from '../api/credentialsApi';
import CredentialForm from './CredentialForm';
import CredentialDisplay from './CredentialDisplay';
import styles from '../styles/credentials.module.css';

interface Opportunity {
  id: string;
  name: string;
  platform: string;
  handle?: string;
}

interface Credential {
  id: string;
  access_type: string;
  status: string;
  credential_username?: string;
  credential_email?: string;
  credential_identifier?: string;
  last_validated_at?: string;
  validation_success?: boolean;
  access_count: number;
  notes?: string;
}

interface AccessMetadata {
  access_type: string;
  enabled: boolean;
  signup_url?: string;
  signup_instructions?: string;
  requires_email?: boolean;
  requires_payment?: boolean;
  rate_limits?: string;
  available_endpoints?: string[];
  testing_account_available?: boolean;
  testing_account_url?: string;
}

interface ScanningModesResponse {
  program_id: string;
  available_modes: string[];
  warnings: Array<{
    type: string;
    access_type: string;
    message: string;
    signup_url?: string;
  }>;
  recommendation: string;
}

export default function CredentialsAccessTab() {
  const { user, token } = useAuth();
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selectedOpportunity, setSelectedOpportunity] = useState<Opportunity | null>(null);
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [accessMetadata, setAccessMetadata] = useState<AccessMetadata[]>([]);
  const [scanningModes, setScanningModes] = useState<ScanningModesResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isValidating, setIsValidating] = useState<string | null>(null);
  const [showCredentialModal, setShowCredentialModal] = useState(false);
  const [selectedAccessType, setSelectedAccessType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Load opportunities on mount
  useEffect(() => {
    loadOpportunities();
  }, []);

  // Load credentials when opportunity selected
  useEffect(() => {
    if (selectedOpportunity) {
      loadCredentialsData();
    }
  }, [selectedOpportunity]);

  const loadOpportunities = async () => {
    try {
      setIsLoading(true);
      const data = await credentialsApi.getOpportunities(token!);
      setOpportunities(data);
      if (data.length > 0) {
        setSelectedOpportunity(data[0]);
      }
    } catch (err) {
      setError(`Failed to load opportunities: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const loadCredentialsData = async () => {
    if (!selectedOpportunity) return;

    try {
      setIsLoading(true);

      // Load stored credentials
      const credsData = await credentialsApi.listCredentials(selectedOpportunity.id, token!);
      setCredentials(credsData.credentials || []);

      // Load access metadata
      const metaData = await credentialsApi.listAccessMetadata(selectedOpportunity.id, token!);
      setAccessMetadata(metaData.metadata || []);

      // Load scanning modes
      const modesData = await credentialsApi.getScanningModes(selectedOpportunity.id, token!);
      setScanningModes(modesData);

      setError(null);
    } catch (err) {
      setError(`Failed to load data: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddCredential = (accessType: string) => {
    setSelectedAccessType(accessType);
    setShowCredentialModal(true);
  };

  const handleSaveCredential = async (formData: any) => {
    if (!selectedOpportunity || !selectedAccessType) return;

    try {
      setIsLoading(true);
      await credentialsApi.storeCredential(
        selectedOpportunity.id,
        selectedAccessType,
        {
          credentials: formData.credentials,
          username: formData.username,
          notes: formData.notes,
        },
        token!
      );

      setSuccess(`${selectedAccessType} credential saved successfully`);
      setShowCredentialModal(false);
      setSelectedAccessType(null);
      await loadCredentialsData();
    } catch (err) {
      setError(`Failed to save credential: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleValidateCredential = async (accessType: string) => {
    if (!selectedOpportunity) return;

    try {
      setIsValidating(accessType);
      const result = await credentialsApi.validateCredential(
        selectedOpportunity.id,
        accessType,
        token!
      );

      if (result.valid) {
        setSuccess(`✓ ${accessType} credential is valid`);
      } else {
        setError(`✗ ${accessType} validation failed: ${result.reason}`);
      }

      await loadCredentialsData();
    } catch (err) {
      setError(`Validation error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsValidating(null);
    }
  };

  const handleDeleteCredential = async (accessType: string) => {
    if (!selectedOpportunity) return;

    if (!window.confirm(`Delete ${accessType} credential? This cannot be undone.`)) {
      return;
    }

    try {
      setIsLoading(true);
      await credentialsApi.deleteCredential(
        selectedOpportunity.id,
        accessType,
        token!
      );

      setSuccess(`${accessType} credential deleted`);
      await loadCredentialsData();
    } catch (err) {
      setError(`Failed to delete credential: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  const getCredentialForType = (accessType: string): Credential | undefined => {
    return credentials.find(c => c.access_type === accessType);
  };

  const getMetadataForType = (accessType: string): AccessMetadata | undefined => {
    return accessMetadata.find(m => m.access_type === accessType);
  };

  if (isLoading && !selectedOpportunity) {
    return <div className={styles.container}><p>Loading...</p></div>;
  }

  return (
    <div className={styles.container}>
      <h1>Credentials & Access Management</h1>

      {error && <div className={styles.alert + ' ' + styles.error}>{error}</div>}
      {success && <div className={styles.alert + ' ' + styles.success}>{success}</div>}

      {/* Opportunity Selector */}
      <section className={styles.section}>
        <h2>Select Opportunity</h2>
        <select
          value={selectedOpportunity?.id || ''}
          onChange={(e) => {
            const opp = opportunities.find(o => o.id === e.target.value);
            setSelectedOpportunity(opp || null);
          }}
          disabled={isLoading}
        >
          <option value="">-- Select an opportunity --</option>
          {opportunities.map(opp => (
            <option key={opp.id} value={opp.id}>
              {opp.name} ({opp.platform})
            </option>
          ))}
        </select>
      </section>

      {selectedOpportunity && (
        <>
          {/* Available Access Types */}
          <section className={styles.section}>
            <h2>Available Access Types</h2>
            <div className={styles.credentialGrid}>
              {['user_account', 'api_key', 'hunter_account'].map(accessType => {
                const credential = getCredentialForType(accessType);
                const metadata = getMetadataForType(accessType);

                return (
                  <div key={accessType} className={styles.credentialCard}>
                    <h3>{formatAccessType(accessType)}</h3>

                    {credential ? (
                      <>
                        <CredentialDisplay credential={credential} accessType={accessType} />
                        <div className={styles.credentialActions}>
                          <button
                            onClick={() => handleValidateCredential(accessType)}
                            disabled={isValidating === accessType}
                          >
                            {isValidating === accessType ? 'Validating...' : 'Validate'}
                          </button>
                          <button
                            onClick={() => handleAddCredential(accessType)}
                            disabled={isLoading}
                          >
                            Update
                          </button>
                          <button
                            onClick={() => handleDeleteCredential(accessType)}
                            disabled={isLoading}
                            className={styles.dangerButton}
                          >
                            Delete
                          </button>
                        </div>
                      </>
                    ) : (
                      <>
                        <p className={styles.noCredential}>No credential stored</p>
                        <button
                          onClick={() => handleAddCredential(accessType)}
                          disabled={isLoading}
                          className={styles.primaryButton}
                        >
                          Add Credential
                        </button>
                      </>
                    )}

                    {metadata && (
                      <div className={styles.metadataSection}>
                        {metadata.signup_url && (
                          <a href={metadata.signup_url} target="_blank" rel="noopener noreferrer">
                            📝 Signup Page
                          </a>
                        )}
                        {metadata.signup_instructions && (
                          <p className={styles.instructions}>{metadata.signup_instructions}</p>
                        )}
                        {accessType === 'api_key' && metadata.rate_limits && (
                          <p className={styles.rateLimit}>
                            <strong>Rate Limit:</strong> {metadata.rate_limits}
                          </p>
                        )}
                        {accessType === 'api_key' && metadata.available_endpoints && (
                          <details>
                            <summary>Available Endpoints</summary>
                            <ul>
                              {metadata.available_endpoints.map((ep, idx) => (
                                <li key={idx}>{ep}</li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* Scanning Modes */}
          {scanningModes && (
            <section className={styles.section}>
              <h2>Available Scanning Modes</h2>
              <div className={styles.scanningModes}>
                {scanningModes.available_modes.map(mode => (
                  <div key={mode} className={styles.modeAvailable}>
                    ✓ {formatScanningMode(mode)}
                  </div>
                ))}
                {scanningModes.warnings.map((warning, idx) => (
                  <div key={idx} className={styles.modeWarning}>
                    ⊘ Missing: {warning.access_type}
                    {warning.signup_url && (
                      <a href={warning.signup_url} target="_blank" rel="noopener noreferrer">
                        Sign up
                      </a>
                    )}
                  </div>
                ))}
              </div>
              <p className={styles.recommendation}>{scanningModes.recommendation}</p>
            </section>
          )}

          {/* Signup Reference */}
          <section className={styles.section}>
            <h2>Quick Signup Reference</h2>
            <details className={styles.signupGuide}>
              <summary>Need User Account?</summary>
              <ol>
                <li>Open signup page (link provided in User Account card)</li>
                <li>Fill form: Email, Password (8+ chars), Name (optional)</li>
                <li>Confirm email from inbox verification link</li>
                <li>Return here and click "Add Credential"</li>
              </ol>
            </details>
            <details className={styles.signupGuide}>
              <summary>Need API Key?</summary>
              <ol>
                <li>Must have user account first (see above)</li>
                <li>Login to the platform</li>
                <li>Go to: Settings → Developer → API Keys</li>
                <li>Click: Create New Key</li>
                <li>Copy key and secret</li>
                <li>Return here and click "Add Credential"</li>
              </ol>
            </details>
            <details className={styles.signupGuide}>
              <summary>Need Hunter Account?</summary>
              <ol>
                <li>Hunter accounts typically provide elevated access</li>
                <li>Click "Sign up" link in Hunter Account card</li>
                <li>Submit application (approval may be required)</li>
                <li>Wait for approval notification</li>
                <li>Return here to add credentials once approved</li>
              </ol>
            </details>
          </section>
        </>
      )}

      {/* Credential Modal */}
      {showCredentialModal && selectedAccessType && (
        <div className={styles.modal}>
          <div className={styles.modalContent}>
            <h2>Add/Update {formatAccessType(selectedAccessType)} Credential</h2>
            <CredentialForm
              accessType={selectedAccessType}
              onSubmit={handleSaveCredential}
              onCancel={() => {
                setShowCredentialModal(false);
                setSelectedAccessType(null);
              }}
              isLoading={isLoading}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function formatAccessType(type: string): string {
  switch (type) {
    case 'user_account':
      return 'User Account';
    case 'api_key':
      return 'API Key';
    case 'hunter_account':
      return 'Hunter Account';
    default:
      return type;
  }
}

function formatScanningMode(mode: string): string {
  switch (mode) {
    case 'unauthenticated':
      return 'Unauthenticated Scanning';
    case 'user_account':
      return 'Authenticated User Scanning';
    case 'api_key':
      return 'API-Based Scanning';
    case 'hunter_account':
      return 'Hunter/Elevated Scanning';
    default:
      return mode;
  }
}

"""API wrapper for credentials endpoints."""
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8080';

export const credentialsApi = {
  /**
   * Get list of all opportunities (for selector)
   */
  async getOpportunities(token: string) {
    const response = await fetch(`${API_BASE}/api/v1/programs`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    if (!response.ok) throw new Error('Failed to fetch opportunities');
    const data = await response.json();
    return data.programs || [];
  },

  /**
   * List all stored credentials for a program (metadata only, no secrets)
   */
  async listCredentials(programId: string, token: string) {
    const response = await fetch(
      `${API_BASE}/api/v1/credentials/${programId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );
    if (!response.ok) throw new Error('Failed to fetch credentials');
    return await response.json();
  },

  /**
   * Store a new credential or update existing
   */
  async storeCredential(
    programId: string,
    accessType: string,
    payload: {
      credentials: any;
      username?: string;
      notes?: string;
    },
    token: string
  ) {
    const response = await fetch(
      `${API_BASE}/api/v1/credentials/${programId}/${accessType}`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      }
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to store credential');
    }
    return await response.json();
  },

  /**
   * Delete a credential
   */
  async deleteCredential(
    programId: string,
    accessType: string,
    token: string
  ) {
    const response = await fetch(
      `${API_BASE}/api/v1/credentials/${programId}/${accessType}`,
      {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete credential');
    }
    return response.status === 204 ? {} : await response.json();
  },

  /**
   * Validate a credential (test if it works)
   */
  async validateCredential(
    programId: string,
    accessType: string,
    token: string
  ) {
    const response = await fetch(
      `${API_BASE}/api/v1/credentials/${programId}/${accessType}/validate`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      }
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Validation failed');
    }
    return await response.json();
  },

  /**
   * Get available scanning modes for a program
   */
  async getScanningModes(programId: string, token: string) {
    const response = await fetch(
      `${API_BASE}/api/v1/credentials/${programId}/scanning-modes`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );
    if (!response.ok) throw new Error('Failed to fetch scanning modes');
    return await response.json();
  },

  /**
   * List access metadata for a program (what access types are available)
   */
  async listAccessMetadata(programId: string, token: string) {
    const response = await fetch(
      `${API_BASE}/api/v1/access-metadata/${programId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );
    if (!response.ok) throw new Error('Failed to fetch access metadata');
    return await response.json();
  },

  /**
   * Update access metadata for a program
   */
  async upsertAccessMetadata(
    programId: string,
    accessType: string,
    payload: any,
    token: string
  ) {
    const response = await fetch(
      `${API_BASE}/api/v1/access-metadata/${programId}/${accessType}`,
      {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      }
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update metadata');
    }
    return await response.json();
  },
};

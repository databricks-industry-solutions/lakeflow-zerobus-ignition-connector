import React, { useState, useEffect } from 'react';
import './App.css';

/**
 * Zerobus Connector Configuration UI
 * 
 * React-based Gateway configuration interface for the Ignition Zerobus Connector module.
 * This UI allows administrators to configure the Databricks connection and tag selection.
 */
function App() {
  const [config, setConfig] = useState({
    workspaceUrl: '',
    zerobusEndpoint: '',
    oauthClientId: '',
    oauthClientSecret: '',
    targetTable: '',
    tagSelectionMode: 'folder',
    tagFolderPath: '',
    tagPathPattern: '',
    explicitTagPaths: [],
    batchSize: 500,
    batchFlushIntervalMs: 2000,
    maxQueueSize: 10000,
    maxEventsPerSecond: 1000,
    enabled: false,
    debugLogging: false
  });

  const [status, setStatus] = useState({
    message: '',
    type: '' // 'success', 'error', 'info'
  });

  const [diagnostics, setDiagnostics] = useState('');
  const [loading, setLoading] = useState(false);

  // Load configuration on mount
  useEffect(() => {
    loadConfiguration();
  }, []);

  const loadConfiguration = async () => {
    try {
      const response = await fetch('/system/zerobus/config');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      setConfig(data);
      
      setStatus({
        message: 'Configuration loaded successfully.',
        type: 'success'
      });
    } catch (error) {
      setStatus({
        message: `Failed to load configuration: ${error.message}`,
        type: 'error'
      });
    }
  };

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setConfig(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleTestConnection = async () => {
    setLoading(true);
    setStatus({ message: 'Testing connection...', type: 'info' });

    try {
      const response = await fetch('/system/zerobus/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const result = await response.json();
      
      if (result.success) {
        setStatus({
          message: result.message || 'Connection test successful!',
          type: 'success'
        });
      } else {
        setStatus({
          message: result.message || 'Connection test failed',
          type: 'error'
        });
      }
    } catch (error) {
      setStatus({
        message: `Connection test failed: ${error.message}`,
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfiguration = async () => {
    setLoading(true);
    setStatus({ message: 'Saving configuration...', type: 'info' });

    try {
      const response = await fetch('/system/zerobus/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      const result = await response.json();
      
      if (result.success) {
        setStatus({
          message: result.message || 'Configuration saved successfully!',
          type: 'success'
        });
      } else {
        setStatus({
          message: result.error || result.details || 'Failed to save configuration',
          type: 'error'
        });
      }
    } catch (error) {
      setStatus({
        message: `Failed to save configuration: ${error.message}`,
        type: 'error'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshDiagnostics = async () => {
    try {
      const response = await fetch('/system/zerobus/diagnostics');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.text();
      setDiagnostics(data);
    } catch (error) {
      setDiagnostics(`Error: ${error.message}`);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Zerobus Connector Configuration</h1>
        <p>Configure Ignition to Databricks streaming via Zerobus Ingest</p>
      </header>

      {status.message && (
        <div className={`status-message ${status.type}`}>
          {status.message}
        </div>
      )}

      <div className="config-container">
        {/* Databricks Connection */}
        <section className="config-section">
          <h2>Databricks Connection</h2>
          
          <div className="form-group">
            <label htmlFor="workspaceUrl">Workspace URL *</label>
            <input
              type="text"
              id="workspaceUrl"
              name="workspaceUrl"
              value={config.workspaceUrl}
              onChange={handleInputChange}
              placeholder="https://your-workspace.cloud.databricks.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="zerobusEndpoint">Zerobus Endpoint *</label>
            <input
              type="text"
              id="zerobusEndpoint"
              name="zerobusEndpoint"
              value={config.zerobusEndpoint}
              onChange={handleInputChange}
              placeholder="https://your-workspace.cloud.databricks.com/api/2.0/..."
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="oauthClientId">OAuth Client ID *</label>
            <input
              type="text"
              id="oauthClientId"
              name="oauthClientId"
              value={config.oauthClientId}
              onChange={handleInputChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="oauthClientSecret">OAuth Client Secret *</label>
            <input
              type="password"
              id="oauthClientSecret"
              name="oauthClientSecret"
              value={config.oauthClientSecret}
              onChange={handleInputChange}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="targetTable">Target Table *</label>
            <input
              type="text"
              id="targetTable"
              name="targetTable"
              value={config.targetTable}
              onChange={handleInputChange}
              placeholder="catalog.schema.table"
              required
            />
          </div>

          <button
            className="btn btn-secondary"
            onClick={handleTestConnection}
            disabled={loading}
          >
            {loading ? 'Testing...' : 'Test Connection'}
          </button>
        </section>

        {/* Tag Selection */}
        <section className="config-section">
          <h2>Tag Selection</h2>

          <div className="form-group">
            <label htmlFor="tagSelectionMode">Selection Mode *</label>
            <select
              id="tagSelectionMode"
              name="tagSelectionMode"
              value={config.tagSelectionMode}
              onChange={handleInputChange}
            >
              <option value="folder">Folder</option>
              <option value="pattern">Pattern</option>
              <option value="explicit">Explicit</option>
            </select>
          </div>

          {config.tagSelectionMode === 'folder' && (
            <div className="form-group">
              <label htmlFor="tagFolderPath">Folder Path *</label>
              <input
                type="text"
                id="tagFolderPath"
                name="tagFolderPath"
                value={config.tagFolderPath}
                onChange={handleInputChange}
                placeholder="[default]Production"
              />
            </div>
          )}

          {config.tagSelectionMode === 'pattern' && (
            <div className="form-group">
              <label htmlFor="tagPathPattern">Path Pattern *</label>
              <input
                type="text"
                id="tagPathPattern"
                name="tagPathPattern"
                value={config.tagPathPattern}
                onChange={handleInputChange}
                placeholder="[default]Conveyor*/Speed"
              />
            </div>
          )}
        </section>

        {/* Performance Settings */}
        <section className="config-section">
          <h2>Performance Settings</h2>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="batchSize">Batch Size</label>
              <input
                type="number"
                id="batchSize"
                name="batchSize"
                value={config.batchSize}
                onChange={handleInputChange}
                min="100"
                max="10000"
              />
            </div>

            <div className="form-group">
              <label htmlFor="batchFlushIntervalMs">Flush Interval (ms)</label>
              <input
                type="number"
                id="batchFlushIntervalMs"
                name="batchFlushIntervalMs"
                value={config.batchFlushIntervalMs}
                onChange={handleInputChange}
                min="100"
                max="60000"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="maxQueueSize">Max Queue Size</label>
              <input
                type="number"
                id="maxQueueSize"
                name="maxQueueSize"
                value={config.maxQueueSize}
                onChange={handleInputChange}
                min="1000"
                max="100000"
              />
            </div>

            <div className="form-group">
              <label htmlFor="maxEventsPerSecond">Max Events/Second</label>
              <input
                type="number"
                id="maxEventsPerSecond"
                name="maxEventsPerSecond"
                value={config.maxEventsPerSecond}
                onChange={handleInputChange}
                min="1"
                max="10000"
              />
            </div>
          </div>
        </section>

        {/* Module Control */}
        <section className="config-section">
          <h2>Module Control</h2>

          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                name="enabled"
                checked={config.enabled}
                onChange={handleInputChange}
              />
              <span>Enable Module</span>
            </label>
          </div>

          <div className="form-group checkbox-group">
            <label>
              <input
                type="checkbox"
                name="debugLogging"
                checked={config.debugLogging}
                onChange={handleInputChange}
              />
              <span>Enable Debug Logging</span>
            </label>
          </div>
        </section>

        {/* Diagnostics */}
        <section className="config-section">
          <h2>Diagnostics</h2>
          
          <button
            className="btn btn-secondary"
            onClick={handleRefreshDiagnostics}
          >
            Refresh Diagnostics
          </button>

          {diagnostics && (
            <pre className="diagnostics-output">{diagnostics}</pre>
          )}
        </section>

        {/* Action Buttons */}
        <div className="action-buttons">
          <button
            className="btn btn-primary"
            onClick={handleSaveConfiguration}
            disabled={loading}
          >
            {loading ? 'Saving...' : 'Save Configuration'}
          </button>
          <button
            className="btn btn-secondary"
            onClick={loadConfiguration}
            disabled={loading}
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;


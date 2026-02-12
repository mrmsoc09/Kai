/**
 * Kaison K1 - RSS Intelligence Dashboard
 * Display vulnerability intelligence from RSS feeds
 * Shows trending topics, latest vulnerabilities, and feed statistics
 */

import React, { useState, useEffect } from 'react';
import { COLORS, UI, BRANDING } from '@/theme/branding';
import './RSSIntelligenceDashboard.css';

interface RSSFeed {
  name: string;
  url: string;
  priority: number;
  last_fetched?: string;
  item_count?: number;
}

interface IntelligenceItem {
  id: string;
  title: string;
  description: string;
  source: string;
  published_date: string;
  cvss_score?: number;
  cve_ids: string[];
  categories: string[];
  relevance_score?: number;
}

interface FeedStats {
  total_feeds: number;
  total_items: number;
  items_today: number;
  items_this_week: number;
  avg_relevance: number;
}

const RSSIntelligenceDashboard: React.FC = () => {
  const [feeds, setFeeds] = useState<RSSFeed[]>([]);
  const [items, setItems] = useState<IntelligenceItem[]>([]);
  const [stats, setStats] = useState<FeedStats>({
    total_feeds: 0,
    total_items: 0,
    items_today: 0,
    items_this_week: 0,
    avg_relevance: 0,
  });
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'date' | 'relevance' | 'cvss'>('date');

  useEffect(() => {
    fetchIntelligenceData();
    const interval = setInterval(fetchIntelligenceData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const fetchIntelligenceData = async () => {
    try {
      // Fetch RSS feeds
      const feedsRes = await fetch('/api/v1/intelligence/feeds');
      const feedsData = await feedsRes.json();

      if (feedsData.success) {
        setFeeds(feedsData.data.feeds || []);
      }

      // Fetch intelligence items
      const itemsRes = await fetch('/api/v1/intelligence/items?limit=50');
      const itemsData = await itemsRes.json();

      if (itemsData.success) {
        setItems(itemsData.data.items || []);
      }

      // Fetch statistics
      const statsRes = await fetch('/api/v1/intelligence/stats');
      const statsData = await statsRes.json();

      if (statsData.success) {
        setStats(statsData.data || stats);
      }

      setLoading(false);
    } catch (error) {
      console.error('Error fetching intelligence data:', error);
      setLoading(false);
    }
  };

  const triggerScan = async () => {
    try {
      setScanning(true);
      const res = await fetch('/api/v1/intelligence/scan', { method: 'POST' });
      const data = await res.json();

      if (data.success) {
        setTimeout(fetchIntelligenceData, 2000); // Refresh after scan
      }
    } catch (error) {
      console.error('Scan failed:', error);
    } finally {
      setScanning(false);
    }
  };

  const getSeverityColor = (cvss?: number): string => {
    if (!cvss) return COLORS.status.info;
    if (cvss >= 9.0) return COLORS.status.critical;
    if (cvss >= 7.0) return COLORS.status.high;
    if (cvss >= 4.0) return COLORS.status.medium;
    return COLORS.status.low;
  };

  const getFilteredItems = () => {
    let filtered = items;

    if (filterCategory !== 'all') {
      filtered = filtered.filter(item => item.categories.includes(filterCategory));
    }

    return filtered.sort((a, b) => {
      if (sortBy === 'date') {
        return new Date(b.published_date).getTime() - new Date(a.published_date).getTime();
      } else if (sortBy === 'relevance') {
        return (b.relevance_score || 0) - (a.relevance_score || 0);
      } else if (sortBy === 'cvss') {
        return (b.cvss_score || 0) - (a.cvss_score || 0);
      }
      return 0;
    });
  };

  const categories = Array.from(new Set(items.flatMap(item => item.categories)));

  if (loading) {
    return (
      <div className="intelligence-loading">
        <div className="spinner"></div>
        <p>Loading intelligence data...</p>
      </div>
    );
  }

  return (
    <div className="rss-intelligence-dashboard" style={{
      backgroundColor: COLORS.background,
      color: COLORS.text
    }}>
      {/* Header */}
      <div className="dashboard-header">
        <div>
          <h1 style={{ color: COLORS.primary.main }}>Threat Intelligence Feed</h1>
          <p style={{ color: COLORS.textSecondary }}>
            Real-time vulnerability intelligence from {stats.total_feeds} RSS sources
          </p>
        </div>
        <button
          onClick={triggerScan}
          disabled={scanning}
          className="scan-button"
          style={{
            backgroundColor: COLORS.primary.main,
            color: COLORS.text
          }}
        >
          {scanning ? 'Scanning...' : 'Scan Now'}
        </button>
      </div>

      {/* Statistics Grid */}
      <div className="stats-grid">
        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.primary.main }}>📰</div>
          <div className="stat-content">
            <h3>{stats.total_feeds}</h3>
            <p>Active Feeds</p>
          </div>
        </div>

        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.status.info }}>📊</div>
          <div className="stat-content">
            <h3>{stats.total_items}</h3>
            <p>Total Items</p>
          </div>
        </div>

        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.status.success }}>🆕</div>
          <div className="stat-content">
            <h3>{stats.items_today}</h3>
            <p>Today</p>
          </div>
        </div>

        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.status.warning }}>📈</div>
          <div className="stat-content">
            <h3>{stats.items_this_week}</h3>
            <p>This Week</p>
          </div>
        </div>
      </div>

      {/* Filters and Controls */}
      <div className="controls-bar" style={{ backgroundColor: COLORS.surface }}>
        <div className="filter-group">
          <label style={{ color: COLORS.text }}>Category:</label>
          <select
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          >
            <option value="all">All Categories</option>
            {categories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label style={{ color: COLORS.text }}>Sort by:</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          >
            <option value="date">Latest First</option>
            <option value="relevance">Relevance</option>
            <option value="cvss">CVSS Score</option>
          </select>
        </div>
      </div>

      {/* Intelligence Items List */}
      <div className="intelligence-items">
        {getFilteredItems().length === 0 ? (
          <div className="empty-state" style={{ backgroundColor: COLORS.surface }}>
            <p>No intelligence items found. Run a scan to fetch latest data.</p>
          </div>
        ) : (
          getFilteredItems().map(item => (
            <div key={item.id} className="intelligence-item" style={{
              backgroundColor: COLORS.surface,
              borderLeft: `4px solid ${getSeverityColor(item.cvss_score)}`
            }}>
              <div className="item-header">
                <div>
                  <h3 style={{ color: COLORS.text }}>{item.title}</h3>
                  <div className="item-meta">
                    <span className="source-badge" style={{ color: COLORS.primary.main }}>
                      {item.source}
                    </span>
                    <span style={{ color: COLORS.textSecondary }}>
                      {new Date(item.published_date).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <div className="item-scores">
                  {item.cvss_score && (
                    <div className="cvss-badge" style={{
                      backgroundColor: getSeverityColor(item.cvss_score) + '20',
                      color: getSeverityColor(item.cvss_score)
                    }}>
                      CVSS: {item.cvss_score.toFixed(1)}
                    </div>
                  )}
                  {item.relevance_score && (
                    <div className="relevance-badge" style={{
                      backgroundColor: COLORS.status.info + '20',
                      color: COLORS.status.info
                    }}>
                      Relevance: {(item.relevance_score * 100).toFixed(0)}%
                    </div>
                  )}
                </div>
              </div>

              <p className="item-description" style={{ color: COLORS.textSecondary }}>
                {item.description}
              </p>

              <div className="item-footer">
                <div className="cve-badges">
                  {item.cve_ids.map(cve => (
                    <span key={cve} className="cve-badge" style={{
                      backgroundColor: COLORS.elevated,
                      color: COLORS.primary.main
                    }}>
                      {cve}
                    </span>
                  ))}
                </div>
                <div className="category-badges">
                  {item.categories.map(cat => (
                    <span key={cat} className="category-badge" style={{
                      backgroundColor: COLORS.elevated,
                      color: COLORS.textSecondary
                    }}>
                      {cat}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Active Feeds Panel */}
      <div className="feeds-panel" style={{ backgroundColor: COLORS.surface }}>
        <h2 style={{ color: COLORS.primary.main }}>Active RSS Feeds</h2>
        <div className="feeds-list">
          {feeds.map((feed, idx) => (
            <div key={idx} className="feed-item" style={{
              backgroundColor: COLORS.elevated,
              borderLeft: `3px solid ${COLORS.primary.main}`
            }}>
              <div className="feed-info">
                <h4 style={{ color: COLORS.text }}>{feed.name}</h4>
                <p style={{ color: COLORS.textSecondary }}>{feed.url}</p>
              </div>
              <div className="feed-stats">
                <span style={{ color: COLORS.status.info }}>
                  Priority: {feed.priority}
                </span>
                {feed.item_count !== undefined && (
                  <span style={{ color: COLORS.status.success }}>
                    Items: {feed.item_count}
                  </span>
                )}
                {feed.last_fetched && (
                  <span style={{ color: COLORS.textSecondary }}>
                    Last: {new Date(feed.last_fetched).toLocaleTimeString()}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default RSSIntelligenceDashboard;

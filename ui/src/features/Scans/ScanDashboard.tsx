import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'
import { Plus, Search, Filter, Download, AlertCircle } from 'lucide-react'
import { format } from 'date-fns'
import type { ScanResult, Finding } from '@/types'

const SEVERITY_COLORS = {
  critical: '#ff3366',
  high: '#ff6b6b',
  medium: '#ffcc00',
  low: '#00f0ff',
  info: '#6b6b8f',
}

export function ScanDashboard() {
  const [selectedScan, setSelectedScan] = useState<ScanResult | null>(null)
  
  const { data: scans, isLoading } = useQuery({
    queryKey: ['scans'],
    queryFn: api.getScans,
  })
  
  const severityData = selectedScan ? [
    { name: 'Critical', value: selectedScan.severityCounts.critical, color: SEVERITY_COLORS.critical },
    { name: 'High', value: selectedScan.severityCounts.high, color: SEVERITY_COLORS.high },
    { name: 'Medium', value: selectedScan.severityCounts.medium, color: SEVERITY_COLORS.medium },
    { name: 'Low', value: selectedScan.severityCounts.low, color: SEVERITY_COLORS.low },
    { name: 'Info', value: selectedScan.severityCounts.info, color: SEVERITY_COLORS.info },
  ] : []
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Scan Results</h1>
        <button className="cyber-button-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          New Scan
        </button>
      </div>
      
      {/* Stats Overview */}
      {selectedScan && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="glass-panel p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Severity Distribution</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={severityData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {severityData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#12121a', 
                      border: '1px solid #252536',
                      borderRadius: '8px'
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap gap-2 justify-center mt-2">
              {severityData.map((item) => (
                <div key={item.name} className="flex items-center gap-1 text-xs">
                  <div className="w-2 h-2 rounded-full" style={{ backgroundColor: item.color }} />
                  <span className="text-kai-400">{item.name}: {item.value}</span>
                </div>
              ))}
            </div>
          </div>
          
          <div className="lg:col-span-2 glass-panel p-6">
            <h3 className="text-lg font-semibold text-white mb-4">Findings Timeline</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={selectedScan.findings.slice(0, 10)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#252536" />
                  <XAxis 
                    dataKey="category" 
                    stroke="#6b6b8f" 
                    fontSize={12}
                    tickLine={false}
                  />
                  <YAxis stroke="#6b6b8f" fontSize={12} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#12121a', 
                      border: '1px solid #252536',
                      borderRadius: '8px'
                    }}
                  />
                  <Bar dataKey="severity" fill="#00f0ff" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
      
      {/* Scan List */}
      <div className="glass-panel">
        <div className="p-4 border-b border-kai-700 flex items-center gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-kai-400" />
            <input 
              type="text" 
              placeholder="Search scans..."
              className="w-full cyber-input pl-10"
            />
          </div>
          <button className="cyber-button flex items-center gap-2">
            <Filter className="w-4 h-4" />
            Filter
          </button>
          <button className="cyber-button flex items-center gap-2">
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-kai-900/50 text-left">
              <tr>
                <th className="px-6 py-3 text-xs font-medium text-kai-400 uppercase tracking-wider">Target</th>
                <th className="px-6 py-3 text-xs font-medium text-kai-400 uppercase tracking-wider">Type</th>
                <th className="px-6 py-3 text-xs font-medium text-kai-400 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-xs font-medium text-kai-400 uppercase tracking-wider">Findings</th>
                <th className="px-6 py-3 text-xs font-medium text-kai-400 uppercase tracking-wider">Start Time</th>
                <th className="px-6 py-3 text-xs font-medium text-kai-400 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-kai-800">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-kai-400">Loading scans...</td>
                </tr>
              ) : scans?.map((scan) => (
                <tr 
                  key={scan.id} 
                  className="hover:bg-kai-800/50 cursor-pointer transition-colors"
                  onClick={() => setSelectedScan(scan)}
                >
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-white">
                    {scan.target}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-kai-300">
                    {scan.scanType}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <ScanStatusBadge status={scan.status} />
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-kai-300">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 text-kai-accent-red" />
                      {scan.findings.length}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-kai-400 font-mono">
                    {format(new Date(scan.startTime), 'MMM dd, HH:mm')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-kai-400">
                    <button className="hover:text-white transition-colors">View</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function ScanStatusBadge({ status }: { status: ScanResult['status'] }) {
  const styles = {
    running: 'bg-kai-accent-cyan/10 text-kai-accent-cyan border-kai-accent-cyan/30',
    completed: 'bg-kai-accent-green/10 text-kai-accent-green border-kai-accent-green/30',
    failed: 'bg-kai-accent-red/10 text-kai-accent-red border-kai-accent-red/30',
  }
  
  return (
    <span className={cn("px-2 py-1 text-xs rounded border", styles[status])}>
      {status}
    </span>
  )
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ')
}

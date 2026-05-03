import { useAgents } from '@/hooks/useAgents'
import { Activity, Zap, Shield, AlertTriangle } from 'lucide-react'
import { format } from 'date-fns'

export function Overview() {
  const { data: agents, isLoading } = useAgents()
  
  const activeAgents = agents?.filter(a => a.status === 'active').length || 0
  const totalAgents = agents?.length || 0
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Security Operations Center</h1>
        <span className="text-sm text-kai-400 font-mono">
          {format(new Date(), 'yyyy-MM-dd HH:mm:ss')}
        </span>
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard 
          title="Active Agents" 
          value={activeAgents} 
          total={totalAgents}
          icon={Zap} 
          color="cyan"
          loading={isLoading}
        />
        <StatCard 
          title="Active Scans" 
          value={3} 
          icon={Activity} 
          color="green"
        />
        <StatCard 
          title="Threats Blocked" 
          value={147} 
          icon={Shield} 
          color="purple"
        />
        <StatCard 
          title="Critical Alerts" 
          value={2} 
          icon={AlertTriangle} 
          color="red"
        />
      </div>
      
      {/* Recent Activity */}
      <div className="glass-panel p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Activity className="w-5 h-5 text-kai-accent-cyan" />
          Recent Activity
        </h2>
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-4 p-3 bg-kai-950/50 rounded-lg border border-kai-800">
              <div className="w-2 h-2 rounded-full bg-kai-accent-cyan" />
              <div className="flex-1">
                <p className="text-sm text-white">Reconnaissance scan completed on target-0{i}.corp</p>
                <p className="text-xs text-kai-400 font-mono mt-1">2 minutes ago</p>
              </div>
              <span className="px-2 py-1 text-xs rounded bg-kai-accent-green/10 text-kai-accent-green border border-kai-accent-green/20">
                Completed
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

interface StatCardProps {
  title: string
  value: number
  total?: number
  icon: React.ElementType
  color: 'cyan' | 'green' | 'purple' | 'red'
  loading?: boolean
}

function StatCard({ title, value, total, icon: Icon, color, loading }: StatCardProps) {
  const colors = {
    cyan: 'text-kai-accent-cyan bg-kai-accent-cyan/10 border-kai-accent-cyan/30',
    green: 'text-kai-accent-green bg-kai-accent-green/10 border-kai-accent-green/30',
    purple: 'text-kai-accent-purple bg-kai-accent-purple/10 border-kai-accent-purple/30',
    red: 'text-kai-accent-red bg-kai-accent-red/10 border-kai-accent-red/30',
  }
  
  return (
    <div className="glass-panel p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-kai-400 text-sm font-medium">{title}</p>
          <div className="mt-2 flex items-baseline gap-2">
            {loading ? (
              <div className="h-8 w-16 bg-kai-800 animate-pulse rounded" />
            ) : (
              <>
                <span className="text-3xl font-bold text-white">{value}</span>
                {total !== undefined && (
                  <span className="text-sm text-kai-400">/ {total}</span>
                )}
              </>
            )}
          </div>
        </div>
        <div className={cn("p-3 rounded-lg border", colors[color])}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  )
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ')
}

import { useState } from 'react'
import { useAgents, useSendCommand, useStopAgent } from '@/hooks/useAgents'
import { 
  Play, 
  Square, 
  Terminal, 
  RefreshCw, 
  MoreVertical,
  Cpu,
  Activity
} from 'lucide-react'
import { cn } from '@/utils/cn'
import type { Agent } from '@/types'

export function AgentControlPanel() {
  const { data: agents, isLoading } = useAgents()
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null)
  const [commandInput, setCommandInput] = useState('')
  
  const sendCommand = useSendCommand()
  const stopAgent = useStopAgent()
  
  const handleSendCommand = () => {
    if (selectedAgent && commandInput.trim()) {
      sendCommand.mutate({
        agentId: selectedAgent.id,
        command: commandInput,
      })
      setCommandInput('')
    }
  }
  
  if (isLoading) {
    return <div className="text-kai-400">Loading agents...</div>
  }
  
  return (
    <div className="h-[calc(100vh-8rem)] flex gap-6">
      {/* Agent List */}
      <div className="w-80 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white">Active Agents</h2>
          <button className="p-2 hover:bg-kai-800 rounded-lg text-kai-400 hover:text-white">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto space-y-2">
          {agents?.map((agent) => (
            <button
              key={agent.id}
              onClick={() => setSelectedAgent(agent)}
              className={cn(
                "w-full p-4 rounded-lg border text-left transition-all",
                selectedAgent?.id === agent.id
                  ? "bg-kai-accent-cyan/10 border-kai-accent-cyan/50"
                  : "bg-kai-900 border-kai-700 hover:border-kai-600"
              )}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <BotIcon type={agent.type} />
                  <span className="font-medium text-white">{agent.name}</span>
                </div>
                <StatusBadge status={agent.status} />
              </div>
              
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-kai-400">Task</span>
                  <span className="text-kai-300 truncate max-w-[120px]">
                    {agent.currentTask || 'Idle'}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-kai-400">Progress</span>
                  <span className="text-kai-accent-cyan">{agent.progress}%</span>
                </div>
                <div className="w-full bg-kai-800 rounded-full h-1.5 mt-2">
                  <div 
                    className="bg-kai-accent-cyan h-1.5 rounded-full transition-all"
                    style={{ width: `${agent.progress}%` }}
                  />
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>
      
      {/* Agent Detail / Control */}
      <div className="flex-1 flex flex-col gap-4">
        {selectedAgent ? (
          <>
            <div className="glass-panel p-6">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h3 className="text-2xl font-bold text-white mb-1">{selectedAgent.name}</h3>
                  <p className="text-kai-400 font-mono text-sm">ID: {selectedAgent.id}</p>
                </div>
                <div className="flex gap-2">
                  {selectedAgent.status === 'active' ? (
                    <button
                      onClick={() => stopAgent.mutate(selectedAgent.id)}
                      className="cyber-button flex items-center gap-2 text-kai-accent-red border-kai-accent-red/50 hover:bg-kai-accent-red/10"
                    >
                      <Square className="w-4 h-4" />
                      Stop
                    </button>
                  ) : (
                    <button className="cyber-button-primary flex items-center gap-2">
                      <Play className="w-4 h-4" />
                      Start
                    </button>
                  )}
                  <button className="cyber-button p-2">
                    <MoreVertical className="w-4 h-4" />
                  </button>
                </div>
              </div>
              
              <div className="grid grid-cols-3 gap-4 mb-6">
                <MetricCard label="Status" value={selectedAgent.status} />
                <MetricCard label="Type" value={selectedAgent.type} />
                <MetricCard 
                  label="Last Seen" 
                  value={new Date(selectedAgent.lastSeen).toLocaleTimeString()} 
                />
              </div>
              
              {selectedAgent.currentTask && (
                <div className="bg-kai-950 rounded-lg p-4 border border-kai-800">
                  <div className="flex items-center gap-2 text-kai-accent-cyan mb-2">
                    <Activity className="w-4 h-4" />
                    <span className="text-sm font-medium">Current Task</span>
                  </div>
                  <p className="text-white font-mono text-sm">{selectedAgent.currentTask}</p>
                </div>
              )}
            </div>
            
            {/* Terminal / Command Interface */}
            <div className="flex-1 glass-panel flex flex-col">
              <div className="p-3 border-b border-kai-700 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-kai-accent-cyan" />
                <span className="text-sm font-medium text-kai-300">Command Interface</span>
              </div>
              
              <div className="flex-1 p-4 font-mono text-sm overflow-y-auto bg-kai-950/50">
                <div className="text-kai-400 mb-2">
                  <span className="text-kai-accent-green">➜</span> 
                  <span className="text-kai-accent-cyan"> ~</span> 
                  <span className="text-kai-300"> Agent ready. Waiting for commands...</span>
                </div>
              </div>
              
              <div className="p-4 border-t border-kai-700">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={commandInput}
                    onChange={(e) => setCommandInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendCommand()}
                    placeholder="Enter command..."
                    className="flex-1 cyber-input font-mono"
                  />
                  <button 
                    onClick={handleSendCommand}
                    className="cyber-button-primary"
                  >
                    Send
                  </button>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-kai-500">
            <div className="text-center">
              <Bot className="w-16 h-16 mx-auto mb-4 opacity-50" />
              <p>Select an agent to view details and control</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: Agent['status'] }) {
  const styles = {
    active: 'bg-kai-accent-green/20 text-kai-accent-green border-kai-accent-green/30',
    idle: 'bg-kai-700/50 text-kai-300 border-kai-600',
    error: 'bg-kai-accent-red/20 text-kai-accent-red border-kai-accent-red/30',
    offline: 'bg-kai-800 text-kai-500 border-kai-700',
  }
  
  return (
    <span className={cn("px-2 py-1 text-xs rounded border", styles[status])}>
      {status}
    </span>
  )
}

function BotIcon({ type }: { type: Agent['type'] }) {
  const colors = {
    recon: 'text-kai-accent-cyan',
    exploit: 'text-kai-accent-red',
    analysis: 'text-kai-accent-purple',
    reporting: 'text-kai-accent-yellow',
  }
  
  return <Cpu className={cn("w-5 h-5", colors[type])} />
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-kai-950/50 rounded-lg p-3 border border-kai-800">
      <p className="text-xs text-kai-400 mb-1">{label}</p>
      <p className="text-white font-medium capitalize">{value}</p>
    </div>
  )
}

function Bot(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 8V4H8" />
      <rect width="16" height="12" x="4" y="8" rx="2" />
      <path d="M2 14h2" />
      <path d="M20 14h2" />
      <path d="M15 13v2" />
      <path d="M9 13v2" />
    </svg>
  )
}

import { useCallback, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Edge,
  type Node,
  Panel,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize, 
  Save, 
  Share2,
  Target,
  Globe,
  ShieldAlert,
  StickyNote
} from 'lucide-react'

const nodeTypes = {
  target: TargetNode,
  subdomain: SubdomainNode,
  service: ServiceNode,
  vulnerability: VulnNode,
  note: NoteNode,
}

const initialNodes: Node[] = [
  {
    id: '1',
    type: 'target',
    position: { x: 400, y: 100 },
    data: { label: 'target.corp', description: 'Primary target domain' },
  },
  {
    id: '2',
    type: 'subdomain',
    position: { x: 200, y: 250 },
    data: { label: 'api.target.corp', description: 'API endpoint' },
  },
  {
    id: '3',
    type: 'subdomain',
    position: { x: 600, y: 250 },
    data: { label: 'admin.target.corp', description: 'Admin panel' },
  },
  {
    id: '4',
    type: 'vulnerability',
    position: { x: 600, y: 400 },
    data: { label: 'SQL Injection', severity: 'Critical', description: 'Auth bypass possible' },
  },
]

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e1-3', source: '1', target: '3', animated: true },
  { id: 'e3-4', source: '3', target: '4', label: 'exploits' },
]

export function MindmapCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  
  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge({ ...params, animated: true }, eds)),
    [setEdges]
  )
  
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode(node)
  }, [])
  
  return (
    <div className="h-[calc(100vh-8rem)] flex gap-6">
      <div className="flex-1 glass-panel overflow-hidden relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          fitView
          className="bg-kai-950"
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#36364d" gap={20} size={1} />
          <Controls className="bg-kai-900 border-kai-700 text-kai-300" />
          <MiniMap 
            className="bg-kai-900 border-kai-700"
            nodeColor={(node) => {
              switch (node.type) {
                case 'target': return '#00f0ff'
                case 'vulnerability': return '#ff3366'
                case 'subdomain': return '#b829dd'
                default: return '#6b6b8f'
              }
            }}
          />
          
          <Panel position="top-right" className="flex gap-2">
            <button className="cyber-button p-2" title="Zoom In">
              <ZoomIn className="w-4 h-4" />
            </button>
            <button className="cyber-button p-2" title="Zoom Out">
              <ZoomOut className="w-4 h-4" />
            </button>
            <button className="cyber-button p-2" title="Fit View">
              <Maximize className="w-4 h-4" />
            </button>
            <button className="cyber-button-primary flex items-center gap-2">
              <Save className="w-4 h-4" />
              Save
            </button>
            <button className="cyber-button flex items-center gap-2">
              <Share2 className="w-4 h-4" />
              Share
            </button>
          </Panel>
        </ReactFlow>
      </div>
      
      {/* Properties Panel */}
      <div className="w-80 glass-panel p-6 overflow-y-auto">
        <h2 className="text-lg font-bold text-white mb-4">Node Properties</h2>
        
        {selectedNode ? (
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-kai-400 mb-1">Label</label>
              <input 
                type="text" 
                value={selectedNode.data.label}
                className="w-full cyber-input"
                readOnly
              />
            </div>
            
            <div>
              <label className="block text-xs font-medium text-kai-400 mb-1">Type</label>
              <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-kai-800 text-kai-300 capitalize">
                {selectedNode.type}
              </span>
            </div>
            
            <div>
              <label className="block text-xs font-medium text-kai-400 mb-1">Description</label>
              <textarea 
                value={selectedNode.data.description || ''}
                className="w-full cyber-input h-24 resize-none"
                placeholder="Add description..."
              />
            </div>
            
            {selectedNode.data.severity && (
              <div>
                <label className="block text-xs font-medium text-kai-400 mb-1">Severity</label>
                <span className={cn(
                  "inline-flex items-center px-2 py-1 rounded text-xs border",
                  selectedNode.data.severity === 'Critical' && "bg-kai-accent-red/10 text-kai-accent-red border-kai-accent-red/30",
                  selectedNode.data.severity === 'High' && "bg-kai-accent-yellow/10 text-kai-accent-yellow border-kai-accent-yellow/30",
                )}>
                  {selectedNode.data.severity}
                </span>
              </div>
            )}
            
            <div className="pt-4 border-t border-kai-700">
              <button className="w-full cyber-button text-kai-accent-red border-kai-accent-red/50 hover:bg-kai-accent-red/10">
                Delete Node
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center text-kai-500 py-8">
            <Network className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-sm">Select a node to view properties</p>
          </div>
        )}
        
        <div className="mt-8 pt-6 border-t border-kai-700">
          <h3 className="text-sm font-semibold text-white mb-3">Legend</h3>
          <div className="space-y-2">
            <LegendItem icon={Target} label="Target" color="text-kai-accent-cyan" />
            <LegendItem icon={Globe} label="Subdomain" color="text-kai-accent-purple" />
            <LegendItem icon={ShieldAlert} label="Vulnerability" color="text-kai-accent-red" />
            <LegendItem icon={StickyNote} label="Note" color="text-kai-400" />
          </div>
        </div>
      </div>
    </div>
  )
}

function TargetNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 bg-kai-900 border-2 border-kai-accent-cyan rounded-lg shadow-lg shadow-kai-accent-cyan/20">
      <div className="flex items-center gap-2">
        <Target className="w-4 h-4 text-kai-accent-cyan" />
        <span className="text-white font-medium text-sm">{data.label}</span>
      </div>
    </div>
  )
}

function SubdomainNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 bg-kai-900 border border-kai-accent-purple rounded-lg">
      <div className="flex items-center gap-2">
        <Globe className="w-4 h-4 text-kai-accent-purple" />
        <span className="text-kai-200 text-sm">{data.label}</span>
      </div>
    </div>
  )
}

function ServiceNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 bg-kai-900 border border-kai-accent-green rounded-lg">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-kai-accent-green" />
        <span className="text-kai-200 text-sm">{data.label}</span>
      </div>
    </div>
  )
}

function VulnNode({ data }: { data: any }) {
  return (
    <div className="px-4 py-2 bg-kai-accent-red/10 border border-kai-accent-red rounded-lg">
      <div className="flex items-center gap-2">
        <ShieldAlert className="w-4 h-4 text-kai-accent-red" />
        <div>
          <div className="text-kai-accent-red text-sm font-medium">{data.label}</div>
          <div className="text-xs text-kai-400">{data.severity}</div>
        </div>
      </div>
    </div>
  )
}

function NoteNode({ data }: { data: any }) {
  return (
    <div className="px-3 py-2 bg-kai-800 border border-kai-600 rounded-lg max-w-[200px]">
      <div className="flex items-start gap-2">
        <StickyNote className="w-4 h-4 text-kai-400 mt-0.5" />
        <span className="text-kai-300 text-xs">{data.label}</span>
      </div>
    </div>
  )
}

function LegendItem({ icon: Icon, label, color }: { icon: any, label: string, color: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <Icon className={cn("w-4 h-4", color)} />
      <span className="text-kai-300">{label}</span>
    </div>
  )
}

function Network(props: React.SVGProps<SVGSVGElement>) {
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
      <rect x="16" y="16" width="6" height="6" rx="1" />
      <rect x="2" y="16" width="6" height="6" rx="1" />
      <rect x="9" y="2" width="6" height="6" rx="1" />
      <path d="M5 16v-3a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v3" />
      <path d="M12 12V8" />
    </svg>
  )
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ')
}

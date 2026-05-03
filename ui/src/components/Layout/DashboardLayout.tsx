import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Bot, 
  ScanLine, 
  Network, 
  FileText, 
  Terminal,
  Settings,
  Bell,
  Menu,
  X
} from 'lucide-react'
import { cn } from '@/utils/cn'

interface DashboardLayoutProps {
  children: React.ReactNode
}

const navigation = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Agents', href: '/agents', icon: Bot },
  { name: 'Scans', href: '/scans', icon: ScanLine },
  { name: 'Mindmap', href: '/mindmap', icon: Network },
  { name: 'Wordlists', href: '/wordlists', icon: FileText },
]

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  
  return (
    <div className="min-h-screen bg-kai-950 flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Sidebar */}
      <aside className={cn(
        "fixed lg:static inset-y-0 left-0 z-50 w-64 bg-kai-900 border-r border-kai-700 transform transition-transform duration-200 ease-in-out",
        sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      )}>
        <div className="h-full flex flex-col">
          {/* Logo */}
          <div className="h-16 flex items-center px-6 border-b border-kai-700">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gradient-to-br from-kai-accent-cyan to-kai-accent-purple rounded-lg flex items-center justify-center">
                <Terminal className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold tracking-tight">
                KAI<span className="text-kai-accent-cyan">.PLATFORM</span>
              </span>
            </div>
            <button 
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden ml-auto text-kai-400 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
          
          {/* Navigation */}
          <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
            {navigation.map((item) => (
              <NavLink
                key={item.name}
                to={item.href}
                className={({ isActive }) => cn(
                  "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all",
                  isActive 
                    ? "bg-kai-accent-cyan/10 text-kai-accent-cyan border border-kai-accent-cyan/30"
                    : "text-kai-300 hover:bg-kai-800 hover:text-white"
                )}
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </NavLink>
            ))}
          </nav>
          
          {/* Bottom section */}
          <div className="p-4 border-t border-kai-700">
            <button className="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-kai-300 hover:bg-kai-800 hover:text-white transition-all">
              <Settings className="w-5 h-5" />
              <span className="text-sm font-medium">Settings</span>
            </button>
          </div>
        </div>
      </aside>
      
      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top header */}
        <header className="h-16 bg-kai-900/50 backdrop-blur-md border-b border-kai-700 flex items-center justify-between px-4 lg:px-8">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 text-kai-400 hover:text-white"
          >
            <Menu className="w-6 h-6" />
          </button>
          
          <div className="flex items-center gap-4 ml-auto">
            <div className="flex items-center gap-2 px-3 py-1.5 bg-kai-800 rounded-full border border-kai-600">
              <div className="w-2 h-2 rounded-full bg-kai-accent-green animate-pulse" />
              <span className="text-xs font-mono text-kai-accent-green">SYSTEM ONLINE</span>
            </div>
            
            <button className="relative p-2 text-kai-400 hover:text-white transition-colors">
              <Bell className="w-5 h-5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-kai-accent-red rounded-full" />
            </button>
            
            <div className="w-8 h-8 rounded-full bg-kai-700 border border-kai-600 flex items-center justify-center">
              <span className="text-xs font-bold text-kai-accent-cyan">OP</span>
            </div>
          </div>
        </header>
        
        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}

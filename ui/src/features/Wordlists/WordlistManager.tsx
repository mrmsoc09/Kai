import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { 
  Upload, 
  Search, 
  Trash2, 
  Download, 
  FileText, 
  Tag,
  MoreHorizontal
} from 'lucide-react'
import { format } from 'date-fns'
import type { Wordlist } from '@/types'

export function WordlistManager() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  
  const { data: wordlists, isLoading } = useQuery({
    queryKey: ['wordlists'],
    queryFn: api.getWordlists,
  })
  
  const filteredWordlists = wordlists?.filter(w => {
    const matchesSearch = w.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         w.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = selectedCategory === 'all' || w.category === selectedCategory
    return matchesSearch && matchesCategory
  })
  
  const categories = ['all', ...new Set(wordlists?.map(w => w.category) || [])]
  
  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Wordlist Manager</h1>
        <button className="cyber-button-primary flex items-center gap-2">
          <Upload className="w-4 h-4" />
          Upload Wordlist
        </button>
      </div>
      
      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-kai-400" />
          <input 
            type="text" 
            placeholder="Search wordlists..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full cyber-input pl-10"
          />
        </div>
        
        <div className="flex gap-2">
          {categories.map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={cn(
                "px-3 py-2 rounded-lg text-sm font-medium transition-all border",
                selectedCategory === cat
                  ? "bg-kai-accent-cyan/10 border-kai-accent-cyan/50 text-kai-accent-cyan"
                  : "bg-kai-900 border-kai-700 text-kai-400 hover:text-white"
              )}
            >
              {cat.charAt(0).toUpperCase() + cat.slice(1)}
            </button>
          ))}
        </div>
      </div>
      
      {/* Wordlist Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          <div className="col-span-full text-center py-12 text-kai-400">Loading wordlists...</div>
        ) : filteredWordlists?.map((wordlist) => (
          <WordlistCard 
            key={wordlist.id} 
            wordlist={wordlist} 
            formatBytes={formatBytes}
          />
        ))}
      </div>
      
      {filteredWordlists?.length === 0 && (
        <div className="text-center py-12 text-kai-500">
          <FileText className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p>No wordlists found matching your criteria</p>
        </div>
      )}
    </div>
  )
}

function WordlistCard({ 
  wordlist, 
  formatBytes 
}: { 
  wordlist: Wordlist
  formatBytes: (bytes: number) => string 
}) {
  return (
    <div className="glass-panel p-5 hover:border-kai-600 transition-all group">
      <div className="flex items-start justify-between mb-4">
        <div className="p-3 bg-kai-800 rounded-lg">
          <FileText className="w-6 h-6 text-kai-accent-cyan" />
        </div>
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button className="p-2 hover:bg-kai-800 rounded text-kai-400 hover:text-white" title="Download">
            <Download className="w-4 h-4" />
          </button>
          <button className="p-2 hover:bg-kai-800 rounded text-kai-400 hover:text-kai-accent-red" title="Delete">
            <Trash2 className="w-4 h-4" />
          </button>
          <button className="p-2 hover:bg-kai-800 rounded text-kai-400 hover:text-white" title="More">
            <MoreHorizontal className="w-4 h-4" />
          </button>
        </div>
      </div>
      
      <h3 className="text-lg font-semibold text-white mb-1 truncate" title={wordlist.name}>
        {wordlist.name}
      </h3>
      <p className="text-sm text-kai-400 mb-4 line-clamp-2 h-10">
        {wordlist.description}
      </p>
      
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-kai-500">Entries</span>
          <span className="text-kai-300 font-mono">{wordlist.entries.toLocaleString()}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-kai-500">Size</span>
          <span className="text-kai-300 font-mono">{formatBytes(wordlist.size)}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-kai-500">Modified</span>
          <span className="text-kai-400 text-xs">
            {format(new Date(wordlist.lastModified), 'MMM dd, yyyy')}
          </span>
        </div>
      </div>
      
      {wordlist.tags.length > 0 && (
        <div className="mt-4 pt-4 border-t border-kai-800 flex flex-wrap gap-2">
          {wordlist.tags.map(tag => (
            <span 
              key={tag} 
              className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs bg-kai-800 text-kai-300"
            >
              <Tag className="w-3 h-3" />
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function cn(...classes: (string | undefined | false)[]) {
  return classes.filter(Boolean).join(' ')
}

import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const apiBase = import.meta.env.VITE_API_BASE || '';

export default function Docs(){
  const [list, setList] = useState<{path:string,name:string,size:number}[]>([]);
  const [current, setCurrent] = useState<string>('');
  const [content, setContent] = useState<string>('Select a doc on the left');

  useEffect(()=>{
    fetch(apiBase + '/docs/index', { credentials: 'include' })
      .then(r=>r.json())
      .then(setList)
      .catch(()=>setList([]));
  },[]);
  useEffect(()=>{
    if(!current) return;
    fetch(apiBase + '/docs/get?path=' + encodeURIComponent(current), {
      credentials: 'include',
    })
      .then(r=> r.ok ? r.text() : Promise.resolve('# Not found'))
      .then(setContent);
  },[current]);

  return (
    <div className='grid grid-cols-12 gap-4 h-full'>
      <aside className='col-span-3 overflow-auto p-2 border-r border-slate-700'>
        <h3 className='text-sm uppercase tracking-wider text-slate-400 mb-2'>Documentation</h3>
        <ul className='space-y-1'>
          {list.map(it=> (
            <li key={it.path}>
              <button className={'w-full text-left px-2 py-1 rounded hover:bg-slate-800 ' + (current===it.path ? 'bg-slate-800 text-cyan-300' : 'text-slate-200')} onClick={()=>setCurrent(it.path)}>
                {it.name}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <main className='col-span-9 overflow-auto p-4 prose prose-invert max-w-none'>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </main>
    </div>
  )
}

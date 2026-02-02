import React from 'react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
export default function KpiMini({series}:{series:number[]}){
  const data = series.map((y,i)=> ({x:i,y}))
  return <div style={{width:160, height:48}}>
    <ResponsiveContainer>
      <AreaChart data={data} margin={{left:0, right:0, top:6, bottom:0}}>
        <defs>
          <linearGradient id="gk" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#7a2a7a" stopOpacity={0.7}/>
            <stop offset="95%" stopColor="#2a5a7a" stopOpacity={0.1}/>
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="y" stroke="#7a2a7a" fill="url(#gk)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  </div>
}

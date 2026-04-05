/**
 * Command Console
 * Natural language command interface for operators
 */

import React, { useState, useEffect, useRef } from 'react'
import {
  Box,
  TextField,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Typography,
  Alert,
  Chip,
} from '@mui/material'
import { Send as SendIcon } from '@mui/icons-material'
import {
  orchestratorApi,
  ChatMessage,
  NLResponse,
} from '../api/orchestrator'

const QUICK_COMMANDS = [
  'Show mission status',
  'List pending approvals',
  'Show critical findings',
  'Pause current mission',
  'Resume mission',
  'What tools are running?',
  'Show API budget status',
  'List discovered assets',
]

interface ConversationMessage extends ChatMessage {
  nlResponse?: NLResponse
}

const CommandConsole: React.FC = () => {
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loadingHistory, setLoadingHistory] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const response = await orchestratorApi.getChatHistory()
        setMessages(response.data)
      } catch (err) {
        console.error('Failed to load chat history:', err)
      } finally {
        setLoadingHistory(false)
      }
    }

    loadHistory()
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendCommand = async (command: string) => {
    if (!command.trim()) return

    setInputValue('')
    setError(null)

    const operatorMsg: ConversationMessage = {
      role: 'operator',
      content: command,
      timestamp: new Date().toISOString(),
    }

    setMessages((prev) => [...prev, operatorMsg])
    setLoading(true)

    try {
      const response = await orchestratorApi.submitCommand({
        command,
      })

      const assistantMsg: ConversationMessage = {
        role: 'assistant',
        content: response.data.result,
        timestamp: new Date().toISOString(),
        nlResponse: response.data,
      }

      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      setError('Failed to process command')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendCommand(inputValue)
    }
  }

  return (
    <Box sx={{ padding: 3, display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Typography variant="h4" sx={{ marginBottom: 2, fontWeight: 'bold' }}>
        Command Console
      </Typography>

      {error && (
        <Alert severity="error" sx={{ marginBottom: 2 }}>
          {error}
        </Alert>
      )}

      {/* Quick Commands */}
      <Box sx={{ marginBottom: 2 }}>
        <Typography variant="caption" sx={{ color: '#888', display: 'block', marginBottom: 1 }}>
          Quick commands:
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {QUICK_COMMANDS.map((cmd) => (
            <Chip
              key={cmd}
              label={cmd}
              size="small"
              onClick={() => handleSendCommand(cmd)}
              sx={{
                background: '#2196f3',
                color: '#fff',
                cursor: 'pointer',
              }}
            />
          ))}
        </Box>
      </Box>

      {/* Chat History */}
      <Card
        sx={{
          flex: 1,
          background: '#0a0a0a',
          border: '1px solid #333',
          marginBottom: 2,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <CardContent
          sx={{
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {loadingHistory ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', padding: 4 }}>
              <CircularProgress />
            </Box>
          ) : messages.length === 0 ? (
            <Typography variant="body2" sx={{ color: '#888', textAlign: 'center', padding: 4 }}>
              No messages yet. Type a command or click a quick command above.
            </Typography>
          ) : (
            <>
              {messages.map((msg, idx) => (
                <Box
                  key={idx}
                  sx={{
                    display: 'flex',
                    justifyContent: msg.role === 'operator' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <Card
                    sx={{
                      maxWidth: '80%',
                      background: msg.role === 'operator' ? '#2196f3' : '#333',
                      color: msg.role === 'operator' ? '#fff' : '#aaa',
                    }}
                  >
                    <CardContent sx={{ padding: 1.5 }}>
                      <Typography variant="body2">{msg.content}</Typography>
                      {msg.nlResponse && (
                        <Box sx={{ marginTop: 1, paddingTop: 1, borderTop: '1px solid #555' }}>
                          <Typography variant="caption" sx={{ color: '#888' }}>
                            <strong>Interpreted as:</strong> {msg.nlResponse.interpreted_as}
                          </Typography>
                          {msg.nlResponse.approval_required && (
                            <Box sx={{ marginTop: 1 }}>
                              <Alert severity="warning" sx={{ padding: 1 }}>
                                Approval required for this action
                              </Alert>
                              <Box sx={{ display: 'flex', gap: 1, marginTop: 1 }}>
                                <Button size="small" variant="contained" color="success">
                                  Approve
                                </Button>
                                <Button size="small" variant="contained" color="error">
                                  Reject
                                </Button>
                              </Box>
                            </Box>
                          )}
                        </Box>
                      )}
                      <Typography variant="caption" sx={{ color: '#666', display: 'block', marginTop: 1 }}>
                        {new Date(msg.timestamp).toLocaleTimeString()}
                      </Typography>
                    </CardContent>
                  </Card>
                </Box>
              ))}
              {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center' }}>
                  <CircularProgress size={24} />
                </Box>
              )}
              <div ref={messagesEndRef} />
            </>
          )}
        </CardContent>
      </Card>

      {/* Input */}
      <Box sx={{ display: 'flex', gap: 1 }}>
        <TextField
          fullWidth
          multiline
          maxRows={3}
          placeholder="Type a command or ask a question..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={loading}
          sx={{
            '& .MuiOutlinedInput-root': {
              background: '#1a1a1a',
              color: '#fff',
            },
          }}
        />
        <Button
          variant="contained"
          onClick={() => handleSendCommand(inputValue)}
          disabled={loading || !inputValue.trim()}
          sx={{ background: '#2196f3' }}
        >
          <SendIcon />
        </Button>
      </Box>
    </Box>
  )
}

export default CommandConsole

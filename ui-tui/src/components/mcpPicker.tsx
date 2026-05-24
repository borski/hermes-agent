import { Box, Text, useInput, useStdout } from '@hermes/ink'
import { useEffect, useMemo, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import type { McpApplyResponse, McpListResponse, McpServerRow } from '../gatewayTypes.js'
import { asRpcResult, rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, useOverlayKeys, windowOffset } from './overlayControls.js'

const VISIBLE = 14
const MIN_WIDTH = 56
const MAX_WIDTH = 110

interface PickerRow extends McpServerRow {
  initialEnabled: boolean
  staged: boolean
}

export function McpPicker({ gw, onClose, sessionId, sys, t }: McpPickerProps) {
  const [rows, setRows] = useState<PickerRow[]>([])
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)
  const [sel, setSel] = useState(0)
  const [saving, setSaving] = useState(false)

  const { stdout } = useStdout()
  const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, (stdout?.columns ?? 80) - 6))

  useEffect(() => {
    gw.request<McpListResponse>('mcp.list', sessionId ? { session_id: sessionId } : {})
      .then(raw => {
        const r = asRpcResult<McpListResponse>(raw)

        if (!r) {
          setErr('invalid response: mcp.list')
          setLoading(false)

          return
        }

        const next = (r.servers ?? []).map<PickerRow>(s => ({
          ...s,
          initialEnabled: s.enabled,
          staged: s.enabled
        }))

        setRows(next)
        setErr('')
        setLoading(false)
      })
      .catch((e: unknown) => {
        setErr(rpcErrorMessage(e))
        setLoading(false)
      })
  }, [gw, sessionId])

  const dirty = useMemo(() => rows.some(r => r.staged !== r.initialEnabled), [rows])
  const enabledCount = useMemo(() => rows.filter(r => r.staged).length, [rows])

  const applyAndClose = () => {
    if (saving) {
      return
    }

    if (!dirty) {
      onClose()

      return
    }

    const enable = rows.filter(r => r.staged && !r.initialEnabled).map(r => r.name)
    const disable = rows.filter(r => !r.staged && r.initialEnabled).map(r => r.name)

    setSaving(true)
    gw.request<McpApplyResponse>('mcp.apply', {
      ...(sessionId ? { session_id: sessionId } : {}),
      disable,
      enable
    })
      .then(raw => {
        const r = asRpcResult<McpApplyResponse>(raw)
        const changed = r?.changed ?? []
        const missing = r?.missing ?? []

        if (changed.length) {
          sys(`MCP: ${changed.length} updated · ${changed.join(', ')}${r?.reloaded ? ' · tools reloaded' : ''}`)
        } else if (!missing.length) {
          sys('MCP selection unchanged.')
        }

        if (missing.length) {
          sys(`MCP: missing servers — ${missing.join(', ')}`)
        }

        setSaving(false)
        onClose()
      })
      .catch((e: unknown) => {
        sys(`MCP apply failed: ${rpcErrorMessage(e)}`)
        setSaving(false)
        onClose()
      })
  }

  useOverlayKeys({ disabled: saving, onBack: onClose, onClose })

  useInput((ch, key) => {
    if (saving) {
      return
    }

    if ((key.upArrow || ch === 'k') && sel > 0) {
      setSel(s => s - 1)

      return
    }

    if ((key.downArrow || ch === 'j') && sel < rows.length - 1) {
      setSel(s => s + 1)

      return
    }

    if (ch === ' ' && rows[sel]) {
      setRows(prev => prev.map((r, i) => (i === sel ? { ...r, staged: !r.staged } : r)))

      return
    }

    if (key.return) {
      applyAndClose()

      return
    }

    const n = parseInt(ch)

    if (n >= 1 && n <= Math.min(9, rows.length)) {
      setSel(n - 1)
    }
  })

  if (loading) {
    return <Text color={t.color.muted}>loading MCP servers…</Text>
  }

  if (err && !rows.length) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.label}>error: {err}</Text>
        <OverlayHint t={t}>Esc/q close</OverlayHint>
      </Box>
    )
  }

  if (!rows.length) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.muted}>no MCP servers configured</Text>
        <Text color={t.color.muted}>add one with `hermes mcp add` then reopen this picker.</Text>
        <OverlayHint t={t}>Esc/q close</OverlayHint>
      </Box>
    )
  }

  const offset = windowOffset(rows.length, sel, VISIBLE)

  return (
    <Box flexDirection="column" width={width}>
      <Text bold color={t.color.accent}>
        MCP Servers
      </Text>

      <Text color={t.color.muted}>
        {enabledCount}/{rows.length} enabled
        {dirty ? ' · pending changes' : ''}
      </Text>

      {offset > 0 && <Text color={t.color.muted}>  ↑ {offset} more</Text>}

      {rows.slice(offset, offset + VISIBLE).map((row, vi) => {
        const i = offset + vi
        const selected = sel === i
        const check = row.staged ? '✓' : ' '
        const stateLabel = row.staged ? 'enabled' : 'disabled'
        const changedMark = row.staged === row.initialEnabled ? ' ' : '•'

        return (
          <Box key={row.name}>
            <Text bold={selected} color={selected ? t.color.accent : t.color.muted} inverse={selected}>
              {selected ? '▸ ' : '  '}
            </Text>

            <Box width={4}>
              <Text bold={selected} color={selected ? t.color.accent : t.color.muted} inverse={selected}>
                [{check}]
              </Text>
            </Box>

            <Box width={28}>
              <Text bold={selected} color={selected ? t.color.accent : t.color.muted} inverse={selected}>
                {row.name}
              </Text>
            </Box>

            <Box width={10}>
              <Text color={selected ? t.color.accent : t.color.muted} inverse={selected}>
                {row.kind}
              </Text>
            </Box>

            <Box width={12}>
              <Text color={row.staged ? t.color.accent : t.color.muted} inverse={selected}>
                {stateLabel} {changedMark}
              </Text>
            </Box>

            <Text color={t.color.muted} inverse={selected} wrap="truncate-end">
              {row.summary ?? ''}
            </Text>
          </Box>
        )
      })}

      {offset + VISIBLE < rows.length && (
        <Text color={t.color.muted}>  ↓ {rows.length - offset - VISIBLE} more</Text>
      )}

      {err && <Text color={t.color.label}>error: {err}</Text>}

      {saving ? (
        <OverlayHint t={t}>applying…</OverlayHint>
      ) : (
        <OverlayHint t={t}>↑/↓ select · SPACE toggle · Enter apply &amp; close · Esc/q cancel</OverlayHint>
      )}
    </Box>
  )
}

interface McpPickerProps {
  gw: GatewayClient
  onClose: () => void
  sessionId: null | string
  sys: (line: string) => void
  t: Theme
}

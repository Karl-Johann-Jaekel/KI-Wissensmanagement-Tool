import type { ReactNode } from 'react'
import type { Citation } from '../types'

/**
 * Minimal Markdown subset for model answers and notes: paragraphs, "- " / "1. " lists,
 * **bold**, and [n] citation chips. Avoids a Markdown dependency and never renders raw HTML.
 */

type Block =
  | { kind: 'p'; lines: string[] }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] }

const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*\d+[.)]\s+(.*)$/
const INLINE = /(\*\*[^*]+\*\*|\[\d+\])/g

function parseBlocks(text: string): Block[] {
  const blocks: Block[] = []
  for (const line of text.split(/\r?\n/)) {
    const bullet = BULLET.exec(line)
    const numbered = bullet ? null : NUMBERED.exec(line)
    const last = blocks.at(-1)
    if (bullet?.[1] !== undefined) {
      if (last?.kind === 'ul') last.items.push(bullet[1])
      else blocks.push({ kind: 'ul', items: [bullet[1]] })
    } else if (numbered?.[1] !== undefined) {
      if (last?.kind === 'ol') last.items.push(numbered[1])
      else blocks.push({ kind: 'ol', items: [numbered[1]] })
    } else if (line.trim() === '') {
      if (last && !(last.kind === 'p' && last.lines.length === 0)) blocks.push({ kind: 'p', lines: [] })
    } else {
      const heading = line.replace(/^#{1,6}\s+/, '')
      const content = heading !== line ? `**${heading}**` : line
      if (last?.kind === 'p') last.lines.push(content)
      else blocks.push({ kind: 'p', lines: [content] })
    }
  }
  return blocks.filter((b) => (b.kind === 'p' ? b.lines.length > 0 : b.items.length > 0))
}

interface RichTextProps {
  text: string
  citations?: Citation[]
  onCitation?: (citation: Citation) => void
}

export function RichText({ text, citations = [], onCitation }: RichTextProps) {
  const byNumber = new Map(citations.map((c) => [c.n, c]))

  const inline = (value: string, keyPrefix: string): ReactNode[] =>
    value.split(INLINE).map((part, i) => {
      const key = `${keyPrefix}-${i}`
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return <strong key={key}>{part.slice(2, -2)}</strong>
      }
      const marker = /^\[(\d+)\]$/.exec(part)
      const citation = marker?.[1] ? byNumber.get(Number(marker[1])) : undefined
      if (citation) {
        return (
          <CitationChip key={key} citation={citation} onClick={onCitation} />
        )
      }
      return part
    })

  return (
    <div className="space-y-2 text-sm leading-relaxed break-words">
      {parseBlocks(text).map((block, i) => {
        if (block.kind === 'ul' || block.kind === 'ol') {
          const Tag = block.kind
          return (
            <Tag key={i} className={`space-y-1 pl-5 ${block.kind === 'ul' ? 'list-disc' : 'list-decimal'}`}>
              {block.items.map((item, j) => (
                <li key={j}>{inline(item, `${i}-${j}`)}</li>
              ))}
            </Tag>
          )
        }
        return (
          <p key={i} className="whitespace-pre-line">
            {inline(block.lines.join('\n'), String(i))}
          </p>
        )
      })}
    </div>
  )
}

function CitationChip({
  citation,
  onClick,
}: {
  citation: Citation
  onClick?: (citation: Citation) => void
}) {
  const label = `${citation.source_title}${citation.page ? `, S. ${citation.page}` : ''}`
  return (
    <button
      type="button"
      onClick={() => onClick?.(citation)}
      title={`${label}\n\n${citation.snippet}`}
      aria-label={`Quelle ${citation.n}: ${label}`}
      className="ml-1 inline-flex h-5 min-w-5 -translate-y-px items-center justify-center rounded-full bg-accent-soft px-1.5 align-middle text-[11px] font-semibold text-accent transition-colors hover:bg-accent hover:text-accent-fg"
    >
      {citation.n}
    </button>
  )
}

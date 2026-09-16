import type { Notebook, Source } from '../types'
import { CloseIcon, FileIcon, LinkIcon, SparkIcon } from './Icons'

/**
 * A map of what the notebook covers, drawn entirely from data that already exists: the source
 * guides' key topics. It costs no LLM call, and every leaf is a question — clicking one asks
 * the chat about that topic, so the map leads back into cited answers.
 */

// Topic labels run long in German ("Technische Komponenten Embedding und Retriever"), so a
// chip gets two lines and the row height follows.
const ROW = 54 // height reserved per topic
const GROUP_GAP = 18 // extra space between two sources
const NOTEBOOK_X = 0
const SOURCE_X = 232
const TOPIC_X = 470
const TOPIC_WIDTH = 300
const WIDTH = TOPIC_X + TOPIC_WIDTH

interface Props {
  notebook: Notebook | undefined
  sources: Source[] | undefined
  onAsk: (question: string) => void
  onOpenSource: (sourceId: string) => void
  onClose: () => void
  className?: string
}

export function TopicMapPanel({
  notebook,
  sources,
  onAsk,
  onOpenSource,
  onClose,
  className = '',
}: Props) {
  const branches = (sources ?? [])
    .filter((s) => s.status === 'ready' && s.key_topics.length > 0)
    .map((s) => ({ source: s, topics: s.key_topics }))

  // Lay the branches out top to bottom; each source sits at the centre of its own topics.
  const blockHeight = (branch: { topics: string[] }) => branch.topics.length * ROW
  const placed = branches.map((branch, index) => {
    const top = branches
      .slice(0, index)
      .reduce((sum, earlier) => sum + blockHeight(earlier) + GROUP_GAP, 0)
    return {
      source: branch.source,
      topics: branch.topics.map((topic, i) => ({ topic, y: top + i * ROW + ROW / 2 })),
      y: top + blockHeight(branch) / 2,
    }
  })
  const height = branches.length
    ? branches.reduce((sum, branch) => sum + blockHeight(branch) + GROUP_GAP, 0) - GROUP_GAP
    : ROW
  const notebookY = height / 2

  return (
    <section className={`panel ${className}`} aria-label="Themenkarte">
      <div className="panel-header">
        <div className="flex min-w-0 items-center gap-2">
          <SparkIcon size={16} className="shrink-0 text-accent" />
          <div className="min-w-0">
            <h2 className="truncate font-medium">Themenkarte</h2>
            <p className="truncate text-xs text-muted">
              Kernthemen aus den Quellen-Guides – ein Klick fragt den Chat danach
            </p>
          </div>
        </div>
        <button className="btn-ghost shrink-0" onClick={onClose}>
          <CloseIcon /> <span className="hidden sm:inline">Zum Chat</span>
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-5">
        {placed.length === 0 ? (
          <p className="text-sm text-muted">
            Sobald die Quellen-Guides fertig sind, erscheinen hier die Kernthemen.
          </p>
        ) : (
          <div className="relative" style={{ width: WIDTH, height }}>
            <svg
              className="absolute inset-0 text-line"
              width={WIDTH}
              height={height}
              aria-hidden="true"
            >
              {placed.map(({ source, topics, y }) => (
                <g key={source.id}>
                  <path
                    d={curve(NOTEBOOK_X + 150, notebookY, SOURCE_X - 6, y)}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={1.5}
                  />
                  {topics.map(({ topic, y: ty }) => (
                    <path
                      key={topic}
                      d={curve(SOURCE_X + 210, y, TOPIC_X - 6, ty)}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1.5}
                    />
                  ))}
                </g>
              ))}
            </svg>

            <div
              className="absolute flex w-[150px] -translate-y-1/2 items-center justify-center rounded-2xl bg-accent px-3 py-2 text-center text-xs font-medium text-accent-fg"
              style={{ left: NOTEBOOK_X, top: notebookY }}
            >
              <span className="line-clamp-3">{notebook?.title ?? 'Notebook'}</span>
            </div>

            {placed.map(({ source, topics, y }) => {
              const TypeIcon = source.type === 'url' ? LinkIcon : FileIcon
              return (
                <div key={source.id}>
                  <button
                    className="absolute flex w-[210px] -translate-y-1/2 items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-left text-xs hover:border-accent"
                    style={{ left: SOURCE_X, top: y }}
                    onClick={() => onOpenSource(source.id)}
                    title={source.title}
                  >
                    <TypeIcon size={14} className="shrink-0 text-muted" />
                    <span className="line-clamp-2">{source.title}</span>
                  </button>
                  {topics.map(({ topic, y: ty }) => (
                    <button
                      key={topic}
                      className="absolute -translate-y-1/2 rounded-2xl border border-line bg-surface-muted px-3 py-1.5 text-left text-xs hover:border-accent hover:bg-accent-soft"
                      style={{ left: TOPIC_X, top: ty, maxWidth: TOPIC_WIDTH }}
                      onClick={() => onAsk(`Was sagen die Quellen zu „${topic}“?`)}
                      title={topic}
                    >
                      <span className="line-clamp-2">{topic}</span>
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}

/** Horizontal bezier between two points, so branches read as one flowing line. */
function curve(x1: number, y1: number, x2: number, y2: number): string {
  const mid = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`
}

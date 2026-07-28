import jsPDF from 'jspdf'

interface ProductFeature { name: string; mentions: number; priority: string }
interface FeatureSignal {
  feature: string; total_mentions: number; fr_mentions: number
  app_count: number; affected_apps: string[]; top_narrative: string | null
}
interface BriefForExport {
  id: string; product_name: string; tagline: string; mode: string; scope: string
  created_at: string; industry: string | null; user_hypothesis: string | null
  core_problem: string; market_gap: string; features: ProductFeature[]
  target_audience: string; differentiation: string; risk: string; risk_level: string
  hypothesis_check: string | null; hypothesis_alignment: string | null
  total_demand: number; apps_analyzed: number; sources: FeatureSignal[]
  concept_description?: string | null
}

const PRIORITY_DE: Record<string, string> = { hoch: 'HOCH', mittel: 'MITTEL', niedrig: 'NIEDRIG' }
const RISK_DE: Record<string, string> = { hoch: 'HOCH', mittel: 'MITTEL', niedrig: 'NIEDRIG' }

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function downloadBriefAsPDF(brief: BriefForExport): void {
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })

  const pageW = 210
  const pageH = 297
  const margin = 18
  const contentW = pageW - 2 * margin
  let y = 0

  // ── helpers ────────────────────────────────────────────────────────────────

  const checkPage = (needed = 10) => {
    if (y + needed > pageH - 14) {
      doc.addPage()
      y = margin
    }
  }

  const text = (str: string, x: number, opts: {
    size?: number; style?: 'normal' | 'bold' | 'italic'
    color?: [number, number, number]; maxW?: number; align?: 'left' | 'center' | 'right'
  } = {}) => {
    const { size = 9, style = 'normal', color = [30, 30, 30], maxW, align = 'left' } = opts
    doc.setFontSize(size)
    doc.setFont('helvetica', style)
    doc.setTextColor(...color)
    if (maxW) {
      const lines = doc.splitTextToSize(str, maxW)
      doc.text(lines, x, y, { align })
      y += lines.length * size * 0.38
    } else {
      doc.text(str, x, y, { align })
      y += size * 0.38
    }
  }

  const gap = (mm = 3) => { y += mm }

  const hRule = (color: [number, number, number] = [220, 220, 230]) => {
    doc.setDrawColor(...color)
    doc.setLineWidth(0.3)
    doc.line(margin, y, pageW - margin, y)
    gap(3)
  }

  const sectionTitle = (label: string, accent: [number, number, number] = [79, 70, 229]) => {
    checkPage(14)
    gap(4)
    doc.setFillColor(...accent)
    doc.rect(margin, y - 3.5, 2.5, 7, 'F')
    text(label.toUpperCase(), margin + 5, { size: 7.5, style: 'bold', color: accent })
    gap(3)
    hRule([220, 220, 235])
  }

  const fieldBlock = (label: string, value: string) => {
    if (!value) return
    const lines = doc.splitTextToSize(value, contentW)
    checkPage(8 + lines.length * 3.8)
    doc.setFontSize(7)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(120, 120, 140)
    doc.text(label.toUpperCase(), margin, y)
    y += 3.5
    doc.setFontSize(9)
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(30, 30, 30)
    doc.text(lines, margin, y)
    y += lines.length * 3.8 + 2.5
  }

  // ── cover header ──────────────────────────────────────────────────────────

  const isCompetitor = brief.mode === 'competitor'
  const headerColor: [number, number, number] = isCompetitor ? [180, 30, 30] : [109, 40, 217]
  const headerBg: [number, number, number] = isCompetitor ? [254, 242, 242] : [245, 243, 255]

  doc.setFillColor(...headerBg)
  doc.rect(0, 0, pageW, 52, 'F')

  y = 14
  const modeLabel = isCompetitor ? 'KONKURRENZPRODUKT' : 'INNOVATIONSPRODUKT'
  doc.setFillColor(...headerColor)
  doc.roundedRect(margin, y - 4, modeLabel.length * 1.85 + 6, 7, 1, 1, 'F')
  doc.setFontSize(6.5)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(255, 255, 255)
  doc.text(modeLabel, margin + 3, y)
  y += 6

  doc.setFontSize(20)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(...headerColor)
  doc.text(brief.product_name, margin, y)
  y += 8

  if (brief.tagline) {
    doc.setFontSize(10)
    doc.setFont('helvetica', 'italic')
    doc.setTextColor(80, 80, 100)
    const tagLines = doc.splitTextToSize(brief.tagline, contentW)
    doc.text(tagLines, margin, y)
    y += tagLines.length * 4.5
  }

  // meta row
  y = 44
  const metaItems = [
    `${brief.total_demand.toLocaleString('de-DE')} Feature-Wünsche`,
    `${brief.apps_analyzed} Apps analysiert`,
    formatDate(brief.created_at),
  ]
  doc.setFontSize(7.5)
  doc.setFont('helvetica', 'normal')
  doc.setTextColor(100, 100, 120)
  doc.text(metaItems.join('  ·  '), margin, y)

  y = 58

  // ── hypothesis check (if guided analysis) ────────────────────────────────

  if (brief.hypothesis_check && brief.hypothesis_alignment) {
    const alignColor: Record<string, [number, number, number]> = {
      stark: [5, 150, 105], mittel: [217, 119, 6], schwach: [220, 38, 38],
    }
    const ac = alignColor[brief.hypothesis_alignment] ?? alignColor.mittel
    const alignLabel: Record<string, string> = { stark: 'Stark validiert', mittel: 'Teilweise validiert', schwach: 'Schwach validiert' }

    doc.setFillColor(ac[0], ac[1], ac[2])
    doc.setGState(doc.GState({ opacity: 0.08 }))
    doc.rect(margin, y - 4, contentW, 28, 'F')
    doc.setGState(doc.GState({ opacity: 1 }))
    doc.setDrawColor(...ac)
    doc.setLineWidth(0.4)
    doc.line(margin, y - 4, margin, y + 24)

    doc.setFontSize(7)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(...ac)
    doc.text(`HYPOTHESEN-CHECK — ${alignLabel[brief.hypothesis_alignment] ?? ''}`.toUpperCase(), margin + 4, y)
    y += 4.5

    doc.setFontSize(8.5)
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(30, 30, 30)
    const hLines = doc.splitTextToSize(brief.hypothesis_check, contentW - 8)
    doc.text(hLines, margin + 4, y)
    y += hLines.length * 3.6 + 6
  }

  // ── core sections ─────────────────────────────────────────────────────────

  sectionTitle('Analyse', [79, 70, 229])
  fieldBlock('Kernproblem', brief.core_problem)
  fieldBlock('Marktlücke', brief.market_gap)
  fieldBlock('Zielgruppe', brief.target_audience)
  fieldBlock('Alleinstellungsmerkmal', brief.differentiation)

  sectionTitle('Kern-Features', [79, 70, 229])
  checkPage(12)

  // feature table header
  doc.setFillColor(245, 245, 252)
  doc.rect(margin, y - 3.5, contentW, 6.5, 'F')
  doc.setFontSize(7)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(100, 100, 130)
  doc.text('FEATURE', margin + 2, y)
  doc.text('ERWÄHNUNGEN', margin + contentW * 0.72, y)
  doc.text('PRIORITÄT', margin + contentW * 0.87, y)
  y += 4

  brief.features.forEach((f, i) => {
    checkPage(8)
    if (i % 2 === 0) {
      doc.setFillColor(250, 250, 253)
      doc.rect(margin, y - 3, contentW, 6.5, 'F')
    }
    const nameLines = doc.splitTextToSize(f.name, contentW * 0.68)
    doc.setFontSize(8.5)
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(30, 30, 30)
    doc.text(nameLines, margin + 2, y)

    doc.setFont('helvetica', 'normal')
    doc.setTextColor(80, 80, 110)
    doc.text(f.mentions.toLocaleString('de-DE'), margin + contentW * 0.72, y)

    const pColor: Record<string, [number, number, number]> = {
      hoch: [185, 28, 28], mittel: [180, 83, 9], niedrig: [4, 120, 87]
    }
    const pc = pColor[f.priority] ?? pColor.mittel
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(...pc)
    doc.text(PRIORITY_DE[f.priority] ?? f.priority, margin + contentW * 0.87, y)

    y += Math.max(nameLines.length * 3.8, 5) + 1.5
  })

  // risk
  sectionTitle('Risiko', [79, 70, 229])
  checkPage(12)
  const riskColor: Record<string, [number, number, number]> = {
    hoch: [185, 28, 28], mittel: [180, 83, 9], niedrig: [4, 120, 87]
  }
  const rc = riskColor[brief.risk_level] ?? riskColor.mittel
  doc.setFillColor(rc[0], rc[1], rc[2])
  doc.setGState(doc.GState({ opacity: 0.08 }))
  doc.rect(margin, y - 3, contentW, 14, 'F')
  doc.setGState(doc.GState({ opacity: 1 }))
  doc.setFontSize(7)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(...rc)
  doc.text(`RISIKOLEVEL: ${RISK_DE[brief.risk_level] ?? brief.risk_level}`, margin + 3, y)
  y += 4
  doc.setFontSize(8.5)
  doc.setFont('helvetica', 'normal')
  doc.setTextColor(30, 30, 30)
  const riskLines = doc.splitTextToSize(brief.risk, contentW - 6)
  doc.text(riskLines, margin + 3, y)
  y += riskLines.length * 3.8 + 6

  // ── concept description ───────────────────────────────────────────────────

  if (brief.concept_description) {
    sectionTitle('Vollständige Konzeptbeschreibung', [79, 70, 229])

    const conceptLines = brief.concept_description.split('\n')
    for (const line of conceptLines) {
      if (line.startsWith('## ')) {
        checkPage(12)
        gap(3)
        doc.setFontSize(11)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(79, 70, 229)
        doc.text(line.slice(3), margin, y)
        y += 5
        hRule([210, 210, 230])
      } else if (line.startsWith('### ')) {
        checkPage(10)
        gap(2)
        doc.setFontSize(9.5)
        doc.setFont('helvetica', 'bold')
        doc.setTextColor(50, 50, 80)
        doc.text(line.slice(4), margin, y)
        y += 4.5
      } else if (line.startsWith('- ') || line.startsWith('* ')) {
        checkPage(7)
        const itemLines = doc.splitTextToSize(line.slice(2), contentW - 6)
        doc.setFontSize(8.5)
        doc.setFont('helvetica', 'normal')
        doc.setTextColor(50, 50, 70)
        doc.text('•', margin + 1, y)
        doc.text(itemLines, margin + 5, y)
        y += itemLines.length * 3.8 + 1
      } else if (/^\d+\.\s/.test(line)) {
        checkPage(7)
        const match = line.match(/^(\d+)\.\s(.*)/)
        if (match) {
          const itemLines = doc.splitTextToSize(match[2], contentW - 7)
          doc.setFontSize(8.5)
          doc.setFont('helvetica', 'normal')
          doc.setTextColor(79, 70, 229)
          doc.text(`${match[1]}.`, margin + 1, y)
          doc.setTextColor(50, 50, 70)
          doc.text(itemLines, margin + 6, y)
          y += itemLines.length * 3.8 + 1
        }
      } else if (line.trim() === '') {
        gap(2)
      } else {
        // Strip **bold** markers for PDF
        const clean = line.replace(/\*\*(.*?)\*\*/g, '$1')
        const pLines = doc.splitTextToSize(clean, contentW)
        checkPage(pLines.length * 3.8 + 3)
        doc.setFontSize(8.5)
        doc.setFont('helvetica', 'normal')
        doc.setTextColor(40, 40, 60)
        doc.text(pLines, margin, y)
        y += pLines.length * 3.8 + 1.5
      }
    }
  }

  // ── data sources (compact) ────────────────────────────────────────────────

  if (brief.sources.length > 0) {
    sectionTitle('Datengrundlage — Signal-Cluster', [79, 70, 229])
    checkPage(10)

    brief.sources.slice(0, 12).forEach((s, i) => {
      checkPage(12)
      if (i % 2 === 0) {
        doc.setFillColor(248, 248, 252)
        doc.rect(margin, y - 3, contentW, 10, 'F')
      }
      doc.setFontSize(8.5)
      doc.setFont('helvetica', 'bold')
      doc.setTextColor(40, 40, 60)
      doc.text(s.feature, margin + 2, y)

      doc.setFont('helvetica', 'normal')
      doc.setFontSize(7.5)
      doc.setTextColor(100, 80, 180)
      doc.text(`${s.fr_mentions} FR`, margin + contentW * 0.58, y)
      doc.setTextColor(80, 80, 100)
      doc.text(`${s.total_mentions} gesamt`, margin + contentW * 0.70, y)
      doc.text(`${s.app_count} App${s.app_count !== 1 ? 's' : ''}`, margin + contentW * 0.87, y)
      y += 4

      if (s.top_narrative) {
        const nLines = doc.splitTextToSize(`"${s.top_narrative.slice(0, 180)}"`, contentW - 4)
        doc.setFontSize(7)
        doc.setFont('helvetica', 'italic')
        doc.setTextColor(120, 120, 140)
        doc.text(nLines, margin + 2, y)
        y += nLines.length * 2.8 + 1
      } else {
        y += 2
      }
    })
  }

  // ── footer on every page ──────────────────────────────────────────────────

  const totalPages = (doc as unknown as { internal: { getNumberOfPages: () => number } }).internal.getNumberOfPages()
  for (let p = 1; p <= totalPages; p++) {
    doc.setPage(p)
    doc.setFillColor(245, 245, 250)
    doc.rect(0, pageH - 10, pageW, 10, 'F')
    doc.setFontSize(6.5)
    doc.setFont('helvetica', 'normal')
    doc.setTextColor(150, 150, 170)
    doc.text('MA Analytics — Innovation Lab', margin, pageH - 4)
    doc.text(`Seite ${p} / ${totalPages}`, pageW - margin, pageH - 4, { align: 'right' })
    if (brief.created_at) {
      doc.text(formatDate(brief.created_at), pageW / 2, pageH - 4, { align: 'center' })
    }
  }

  const filename = `${brief.product_name.replace(/[^a-zA-Z0-9äöüÄÖÜß\s]/g, '').trim().replace(/\s+/g, '_')}_Konzept.pdf`
  doc.save(filename)
}

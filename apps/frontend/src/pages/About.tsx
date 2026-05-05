import {
  MessageCircle, Cpu, Brain, Search, Github, ArrowRight,
  Shield, Code2, User, Ban, Rocket, Send,
} from 'lucide-react'
import { Card } from '../components/Card'
import { cn } from '../utils/cn'

// ── Primitives ────────────────────────────────────────────────────────────────

function Section({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn('space-y-4', className)}>{children}</section>
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-lg font-semibold text-foreground">{children}</h2>
}

function Paragraph({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-muted-foreground leading-relaxed">{children}</p>
}

function FeatureList({ items }: { items: { icon: React.ElementType; text: string }[] }) {
  return (
    <ul className="space-y-2.5">
      {items.map(({ icon: Icon, text }) => (
        <li key={text} className="flex items-start gap-3">
          <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-primary/10">
            <Icon className="h-3 w-3 text-primary" />
          </div>
          <span className="text-sm text-muted-foreground leading-relaxed">{text}</span>
        </li>
      ))}
    </ul>
  )
}

// ── Pipeline flow ─────────────────────────────────────────────────────────────

const PIPELINE_STEPS = [
  { icon: MessageCircle, label: 'Enviar', sub: 'WhatsApp ou Telegram' },
  { icon: Cpu,           label: 'Processar', sub: 'OCR, transcrição, IA' },
  { icon: Brain,         label: 'Analisar', sub: 'Embeddings + resumo' },
  { icon: Search,        label: 'Buscar', sub: 'Semântica e contextual' },
]

function PipelineFlow() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {PIPELINE_STEPS.map(({ icon: Icon, label, sub }, i) => (
        <div key={label} className="flex items-center gap-2">
          <div className="flex flex-col items-center gap-1.5 rounded-xl border border-border bg-muted/40 px-4 py-3 text-center min-w-[90px]">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <Icon className="h-4 w-4 text-primary" />
            </div>
            <span className="text-xs font-medium text-foreground">{label}</span>
            <span className="text-[10px] text-muted-foreground leading-tight">{sub}</span>
          </div>
          {i < PIPELINE_STEPS.length - 1 && (
            <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground/40" />
          )}
        </div>
      ))}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export function About() {
  return (
    <div className="space-y-8 animate-fade-in">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Sobre o Keepiu</h1>
        <p className="mt-1 text-muted-foreground">Um sistema pessoal de conhecimento com IA</p>
      </div>

      {/* O que é */}
      <Section>
        <SectionTitle>O que é o Keepiu</SectionTitle>
        <Paragraph>
          Keepiu é uma ferramenta open source de uso pessoal que transforma conteúdo capturado
          em conhecimento estruturado e pesquisável. Funciona como um "second brain" automatizado:
          você envia, o sistema processa, organiza e torna tudo acessível via busca semântica.
        </Paragraph>
        <FeatureList items={[
          { icon: User,    text: 'Projetado para uso individual — não é SaaS, não tem planos' },
          { icon: Brain,   text: 'IA integrada para resumo, categorização e busca contextual' },
          { icon: Shield,  text: 'Self-hosted: seus dados ficam na sua infraestrutura' },
          { icon: Code2,   text: 'Open source, sem lock-in, sem dependência de serviços externos' },
        ]} />
      </Section>

      {/* Como funciona */}
      <Section>
        <SectionTitle>Como funciona</SectionTitle>
        <Paragraph>
          O fluxo é simples: você envia um conteúdo pelo bot, o pipeline processa automaticamente
          e o resultado fica disponível para busca semântica.
        </Paragraph>
        <PipelineFlow />
        <Paragraph>
          O processamento inclui OCR em imagens, transcrição de áudios e vídeos, extração de
          metadados de links e análise via IA para gerar resumo, tags e categoria.
        </Paragraph>
      </Section>

      {/* RAG pessoal */}
      <Section>
        <SectionTitle>RAG pessoal</SectionTitle>
        <Paragraph>
          Cada conteúdo capturado vira um embedding vetorial. Isso permite buscas que entendem
          contexto e intenção, não apenas palavras-chave.
        </Paragraph>
        <Card className="p-4 bg-muted/40 border-dashed">
          <p className="text-xs text-muted-foreground italic">
            "me mostra conteúdos sobre marketing para academias"
          </p>
          <p className="mt-1 text-xs text-primary">
            → encontra posts salvos sobre fitness, nutrição e captação de alunos, mesmo sem essas palavras exatas
          </p>
        </Card>
      </Section>

      {/* Bot-first */}
      <Section>
        <SectionTitle>Bot-first</SectionTitle>
        <Paragraph>
          A captura acontece pelo celular, sem fricção. Você encaminha um link, áudio, imagem
          ou texto diretamente para o bot no WhatsApp ou Telegram — sem abrir um app, sem
          copiar URL, sem contexto de troca.
        </Paragraph>
        <FeatureList items={[
          { icon: Send,         text: 'Entrada via Telegram e WhatsApp' },
          { icon: MessageCircle,text: 'Suporte a texto, link, imagem, áudio, vídeo e arquivo' },
          { icon: Cpu,          text: 'Processamento assíncrono em background' },
        ]} />
      </Section>

      {/* Filosofia */}
      <Section>
        <SectionTitle>Filosofia</SectionTitle>
        <FeatureList items={[
          { icon: Shield, text: 'Self-hosted first — controle total dos seus dados' },
          { icon: Code2,  text: 'Open source — transparência e liberdade de modificar' },
          { icon: User,   text: 'Uso individual — sem multitenancy, sem contas compartilhadas' },
          { icon: Ban,    text: 'Sem lock-in — você pode exportar e mover tudo a qualquer momento' },
        ]} />
      </Section>

      {/* O que NÃO é */}
      <Section>
        <SectionTitle>O que o Keepiu não é</SectionTitle>
        <ul className="space-y-1.5">
          {[
            'Não é um SaaS — não há assinatura nem planos pagos',
            'Não é uma ferramenta colaborativa — sem times ou espaços compartilhados',
            'Não é um app de notas tradicional — não substitui Notion ou Obsidian',
            'Não é um chatbot — o bot é apenas o canal de entrada',
          ].map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm text-muted-foreground">
              <Ban className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
              {item}
            </li>
          ))}
        </ul>
      </Section>

      {/* Roadmap */}
      <Section>
        <SectionTitle>Roadmap</SectionTitle>
        <ul className="space-y-2">
          {[
            { label: 'Captura de conteúdo do LinkedIn', status: 'Em breve' },
            { label: 'Melhorias de UX na Library e Search', status: 'Em progresso' },
            { label: 'Evolução do pipeline de processamento', status: 'Contínuo' },
          ].map(({ label, status }) => (
            <li key={label} className="flex items-center justify-between gap-4 rounded-lg border border-border px-3 py-2">
              <div className="flex items-center gap-2">
                <Rocket className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />
                <span className="text-sm text-foreground">{label}</span>
              </div>
              <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {status}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      {/* Links */}
      <Section>
        <SectionTitle>Links</SectionTitle>
        <div className="flex flex-wrap gap-3">
          <a
            href="https://github.com/ioit-solutions/bot-content"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-muted transition-colors"
          >
            <Github className="h-4 w-4" />
            GitHub
          </a>
        </div>
      </Section>

    </div>
  )
}

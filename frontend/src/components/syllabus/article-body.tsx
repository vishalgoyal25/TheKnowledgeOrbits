import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Server-rendered article body for /topics/<slug> (G3.13).
 *
 * react-markdown 10 has no hooks and renders in a Server Component, so the
 * words land in the initial HTML — the whole point of this page for search.
 * Element styling mirrors the knowledge-map reader (there is no typography
 * plugin in this project); the reader's Cloudinary infographic and callout
 * renderers stay client-side, so those blockquotes render here as plain quotes.
 */
export default function ArticleBody({ markdown }: { markdown: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ ...props }) => (
          <h1
            className="text-2xl font-bold mt-8 mb-4 text-foreground border-b border-border pb-2 break-words"
            {...props}
          />
        ),
        h2: ({ ...props }) => (
          <h2
            className="text-lg sm:text-xl font-bold mt-8 mb-3 text-primary break-words"
            {...props}
          />
        ),
        h3: ({ ...props }) => (
          <h3
            className="text-sm font-bold mt-6 mb-2 text-indigo-700 uppercase tracking-wider border-b border-indigo-100 pb-1.5 break-words"
            {...props}
          />
        ),
        p: ({ ...props }) => (
          <p
            className="mb-3 leading-relaxed text-[15px] text-foreground/90 break-words"
            {...props}
          />
        ),
        ul: ({ ...props }) => (
          <ul
            className="list-disc pl-5 mb-3 space-y-1 text-[15px] text-foreground/90"
            {...props}
          />
        ),
        ol: ({ ...props }) => (
          <ol
            className="list-decimal pl-5 mb-3 space-y-1 text-[15px] text-foreground/90"
            {...props}
          />
        ),
        li: ({ ...props }) => (
          <li className="leading-relaxed marker:text-primary" {...props} />
        ),
        table: ({ ...props }) => (
          <div className="my-4 overflow-x-auto rounded-lg border border-blue-100">
            <table className="w-full text-sm border-collapse" {...props} />
          </div>
        ),
        thead: ({ ...props }) => <thead className="bg-blue-50" {...props} />,
        th: ({ ...props }) => (
          <th
            className="px-3 py-2 text-left text-xs font-semibold text-blue-700 uppercase tracking-wider border-b border-blue-200 bg-blue-50"
            {...props}
          />
        ),
        td: ({ ...props }) => (
          <td
            className="px-3 py-2 text-sm text-foreground/90 border-b border-blue-100 border-r border-r-blue-100/60 last:border-r-0 align-top break-words"
            {...props}
          />
        ),
        tr: ({ ...props }) => <tr className="even:bg-blue-50/30" {...props} />,
        strong: ({ ...props }) => (
          <strong className="font-semibold text-foreground" {...props} />
        ),
        blockquote: ({ ...props }) => (
          <blockquote
            className="my-4 border-l-4 border-primary/30 pl-4 py-1 bg-muted/30 rounded-r-lg text-sm leading-relaxed text-foreground/85"
            {...props}
          />
        ),
        a: ({ ...props }) => (
          <a className="text-primary underline underline-offset-2" {...props} />
        ),
      }}
    >
      {markdown}
    </ReactMarkdown>
  );
}

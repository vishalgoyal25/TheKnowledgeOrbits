/**
 * Article content renderer — parses markdown-like content into styled HTML
 */

'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Props {
    content: string;
}

export default function ArticleContent({ content }: Props) {
    return (
        <article className="prose prose-lg max-w-none">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    h1: ({ node, ...props }) => <h1 className="text-3xl font-bold mt-8 mb-4" {...props} />,
                    h2: ({ node, ...props }) => <h2 className="text-2xl font-bold mt-6 mb-3" {...props} />,
                    h3: ({ node, ...props }) => <h3 className="text-xl font-bold mt-4 mb-2" {...props} />,
                    p: ({ node, ...props }) => <p className="mb-4 leading-relaxed text-gray-800" {...props} />,
                    ul: ({ node, ...props }) => <ul className="list-disc pl-6 mb-4 space-y-2" {...props} />,
                    ol: ({ node, ...props }) => <ol className="list-decimal pl-6 mb-4 space-y-2" {...props} />,
                    blockquote: ({ node, ...props }) => (
                        <blockquote className="border-l-4 border-gray-300 pl-4 italic my-4 text-gray-700" {...props} />
                    ),
                    code: ({ node, inline, ...props }: any) =>
                        inline ? (
                            <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono" {...props} />
                        ) : (
                            <code className="block bg-gray-100 p-4 rounded-lg my-4 text-sm font-mono overflow-x-auto" {...props} />
                        ),
                }}
            >
                {content}
            </ReactMarkdown>
        </article>
    );
}

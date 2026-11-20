import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Multi-Agent AI Workspace',
  description: 'Clean, modern Multi-Agent AI Task Automation Control Center featuring LangGraph coordination and RAG knowledge base.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Anti-flash theme script: immediately sets theme class before paint */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var stored = localStorage.getItem('theme');
                  var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                  if (stored === 'dark' || (!stored && prefersDark)) {
                    document.documentElement.classList.add('dark');
                  } else {
                    document.documentElement.classList.remove('dark');
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="bg-white dark:bg-black text-neutral-900 dark:text-neutral-100 min-h-screen overflow-hidden antialiased">
        {children}
      </body>
    </html>
  );
}

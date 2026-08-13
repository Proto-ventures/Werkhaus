import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { ThemeProvider } from 'next-themes'
import { Masthead } from '@/components/shell'
import { Toaster } from '@/components/ui/sonner'
import { CompanyList } from '@/routes/CompanyList'
import { Landing } from '@/routes/Landing'
import { Studio } from '@/routes/Studio'

export default function App() {
  return (
    // Light is the design and stays the default, so no system sniffing: a
    // first visit looks the way the page was drawn, and dark is a choice the
    // reader makes and we then remember.
    //
    // disableTransitionOnChange is deliberately absent: the toggle runs the
    // swap inside a view transition, and that prop exists to suppress exactly
    // that.
    <ThemeProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
    >
      <BrowserRouter>
        <Chrome />
        <Toaster position="bottom-right" />
      </BrowserRouter>
    </ThemeProvider>
  )
}

function Chrome() {
  // The studio owns its whole viewport and brings its own chrome.
  const { pathname } = useLocation()
  const inStudio = pathname.startsWith('/c/')

  if (inStudio) {
    return (
      <Routes>
        <Route path="/c/:cid" element={<Studio />} />
        <Route path="/c/:cid/:section" element={<Studio />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    )
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <Masthead />
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/companies" element={<CompanyList />} />
          {/* The interview lives in the studio chat now; the front-door box is
              the only way in. */}
          <Route path="/new" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
      <Footer />
    </div>
  )
}

function Footer() {
  return (
    <footer className="border-rule mt-auto border-t">
      <div className="text-ink-faint mx-auto flex max-w-6xl flex-wrap items-center gap-x-5 gap-y-1 px-4 py-4 font-mono text-[0.6875rem] sm:px-6">
        <span>werkhaus</span>
      </div>
    </footer>
  )
}

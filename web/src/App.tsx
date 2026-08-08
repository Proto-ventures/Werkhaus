import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { Masthead } from '@/components/shell'
import { Toaster } from '@/components/ui/sonner'
import { CompanyList } from '@/routes/CompanyList'
import { Landing } from '@/routes/Landing'
import { Studio } from '@/routes/Studio'

export default function App() {
  return (
    <BrowserRouter>
      <Chrome />
      <Toaster position="bottom-right" />
    </BrowserRouter>
  )
}

function Chrome() {
  // On the front door the masthead carries no navigation: there is one thing to
  // do on that page and it is the box. The studio owns its whole viewport and
  // brings its own chrome.
  const { pathname } = useLocation()
  const onLanding = pathname === '/'
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
      <Masthead minimal={onLanding} />
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
        <Link to="/companies" className="hover:text-ink">
          companies
        </Link>
      </div>
    </footer>
  )
}

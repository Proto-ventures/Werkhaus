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
import { CompanyBoard } from '@/routes/CompanyBoard'
import { CompanyList } from '@/routes/CompanyList'
import { Landing } from '@/routes/Landing'
import { NewCompany } from '@/routes/NewCompany'

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
  // do on that page and it is the box.
  const onLanding = useLocation().pathname === '/'
  return (
    <div className="flex min-h-dvh flex-col">
      <Masthead minimal={onLanding} />
      <div className="flex-1">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/companies" element={<CompanyList />} />
          <Route path="/new" element={<NewCompany />} />
          {/* The dashboard is one page. Old bookmarked sub-routes land on it
              with that section opened. */}
          <Route path="/c/:cid" element={<CompanyBoard />} />
          <Route path="/c/:cid/:section" element={<CompanyBoard />} />
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

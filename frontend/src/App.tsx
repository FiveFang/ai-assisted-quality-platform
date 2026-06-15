import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { RequirementsListPage } from '@/pages/RequirementsListPage'
import { AnalyzePage } from '@/pages/AnalyzePage'
import { RAAReviewPage } from '@/pages/RAAReviewPage'
import { TGAReviewPage } from '@/pages/TGAReviewPage'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<RequirementsListPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/requirements/:id" element={<RAAReviewPage />} />
          <Route path="/tests/:id" element={<TGAReviewPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}

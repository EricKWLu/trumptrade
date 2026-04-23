import { createBrowserRouter } from "react-router-dom"
import AppShell from "./components/AppShell"
import FeedPage from "./pages/FeedPage"
import TradesPage from "./pages/TradesPage"
import PortfolioPage from "./pages/PortfolioPage"
import SettingsPage from "./pages/SettingsPage"
import BenchmarksPage from "./pages/BenchmarksPage"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <FeedPage /> },           // CRITICAL: index:true, NOT path:"/"
      { path: "trades", element: <TradesPage /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "benchmarks", element: <BenchmarksPage /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
])

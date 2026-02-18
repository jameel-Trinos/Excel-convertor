"use client";

import { useState } from "react";
import { NavigationMenu, type MenuItem } from "@/components/NavigationMenu";
import {
  ElectionResultsView,
  BoothView,
  ConstituencyView,
  VotersView,
} from "@/components/views";

export default function Home() {
  const [currentView, setCurrentView] = useState<MenuItem>("election-results");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const getMenuLabel = (view: MenuItem): string => {
    const labels: Record<MenuItem, string> = {
      "election-results": "Election Results",
      "booth": "Booth",
      "constituency": "Constituency",
      "voters": "Voters",
    };
    return labels[view];
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-gray-100">
      {/* Navigation Sidebar */}
      <NavigationMenu
        currentView={currentView}
        onViewChange={setCurrentView}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Header */}
      <Header onMenuToggle={() => setSidebarOpen(!sidebarOpen)} />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
        {/* Menu Name Display */}
        <div className="mb-6">
          <h2 className="text-3xl font-bold text-gray-900">{getMenuLabel(currentView)}</h2>
        </div>

        {/* Content based on current view - each view is completely isolated */}
        {currentView === "election-results" && <ElectionResultsView />}
        {currentView === "booth" && <BoothView />}
        {currentView === "constituency" && <ConstituencyView />}
        {currentView === "voters" && <VotersView />}

      </main>

      {/* Footer */}
      <Footer />
    </div>
  );
}

// Header Component
function Header({ onMenuToggle }: { onMenuToggle: () => void }) {
  return (
    <header className="bg-white shadow-sm border-b border-gray-200 sticky top-0 z-30">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Menu Toggle Button */}
            <button
              onClick={onMenuToggle}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
              aria-label="Toggle menu"
            >
              <svg
                className="w-6 h-6 text-gray-700"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-gray-900">PDF to Excel Converter</h1>
              <p className="text-sm text-gray-500">Convert election results in seconds</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

// Footer
function Footer() {
  return (
    <footer className="bg-white border-t border-gray-200 mt-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <p className="text-center text-sm text-gray-600">
          © {new Date().getFullYear()} PDF to Excel Converter. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

"use client";

import { FileUpload } from "@/components/FileUpload";
import { FileSpreadsheet, Zap, Shield, Clock } from "lucide-react";

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="container mx-auto px-4 py-8 md:py-16">
        {/* Header */}
        <div className="text-center mb-8 md:mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <FileSpreadsheet className="h-10 w-10 md:h-12 md:w-12 text-blue-600" />
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900">
              PDF to Excel Converter
            </h1>
          </div>
          <p className="text-gray-600 text-lg max-w-2xl mx-auto">
            Convert your tabular PDFs to professionally formatted Excel
            spreadsheets in seconds. No registration required.
          </p>
        </div>

        {/* Main Upload Area */}
        <div className="max-w-2xl mx-auto mb-12">
          <FileUpload />
        </div>

        {/* Features */}
        <div className="max-w-4xl mx-auto">
          <h2 className="text-center text-xl font-semibold text-gray-800 mb-6">
            Why Choose Our Converter?
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <FeatureCard
              icon={<Zap className="h-8 w-8 text-yellow-500" />}
              title="Lightning Fast"
              description="Convert your PDFs in seconds with our optimized extraction engine"
            />
            <FeatureCard
              icon={<Shield className="h-8 w-8 text-green-500" />}
              title="Privacy First"
              description="Your files are processed securely and automatically deleted after conversion"
            />
            <FeatureCard
              icon={<Clock className="h-8 w-8 text-blue-500" />}
              title="No Limits"
              description="Convert as many files as you need, up to 10MB per file"
            />
          </div>
        </div>

        {/* How It Works */}
        <div className="max-w-4xl mx-auto mt-12">
          <h2 className="text-center text-xl font-semibold text-gray-800 mb-6">
            How It Works
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StepCard
              number={1}
              title="Upload"
              description="Drag and drop your PDF or click to browse"
            />
            <StepCard
              number={2}
              title="Convert"
              description="We extract tables and apply professional formatting"
            />
            <StepCard
              number={3}
              title="Download"
              description="Get your formatted Excel file instantly"
            />
          </div>
        </div>

        {/* Footer */}
        <footer className="text-center mt-16 text-gray-500 text-sm">
          <p>PDF to Excel Converter - Fast, Free, and Secure</p>
        </footer>
      </div>
    </main>
  );
}

function FeatureCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100 text-center">
      <div className="flex justify-center mb-4">{icon}</div>
      <h3 className="font-semibold text-gray-800 mb-2">{title}</h3>
      <p className="text-gray-600 text-sm">{description}</p>
    </div>
  );
}

function StepCard({
  number,
  title,
  description,
}: {
  number: number;
  title: string;
  description: string;
}) {
  return (
    <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-100 text-center relative">
      <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
        <span className="bg-blue-600 text-white text-sm font-bold rounded-full w-7 h-7 flex items-center justify-center">
          {number}
        </span>
      </div>
      <h3 className="font-semibold text-gray-800 mt-2 mb-2">{title}</h3>
      <p className="text-gray-600 text-sm">{description}</p>
    </div>
  );
}

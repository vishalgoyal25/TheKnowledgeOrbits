/**
 * Enhanced home page
 */

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Sparkles, BookOpen, Target, Zap } from 'lucide-react';

export default function HomePage() {
  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-b from-blue-50 to-white py-20">
        <div className="container mx-auto px-4 text-center">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Master UPSC with
            <span className="text-blue-600"> AI-Powered</span> Learning
          </h1>

          <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
            Get personalized, RAG-generated articles tailored to your syllabus.
            Learn faster, retain better, ace your exams.
          </p>

          <div className="flex gap-4 justify-center">
            <Link href="/generate">
              <Button size="lg" className="gap-2 bg-blue-600 hover:bg-blue-700">
                <Sparkles className="h-5 w-5" />
                Generate AI Article
              </Button>
            </Link>

            <Link href="/articles">
              <Button size="lg" variant="outline" className="gap-2">
                <BookOpen className="h-5 w-5" />
                Explore Articles
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="py-20">
        <div className="container mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-12">
            Why TheKnowledgeOrbits?
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="bg-blue-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <Sparkles className="h-8 w-8 text-blue-600" />
              </div>
              <h3 className="text-xl font-bold mb-2">AI-Generated Content</h3>
              <p className="text-gray-600">
                Articles generated from verified NCERT sources using RAG technology
              </p>
            </div>

            <div className="text-center">
              <div className="bg-green-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <Target className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="text-xl font-bold mb-2">Syllabus-Focused</h3>
              <p className="text-gray-600">
                Every topic mapped to UPSC syllabus for targeted preparation
              </p>
            </div>

            <div className="text-center">
              <div className="bg-purple-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
                <Zap className="h-8 w-8 text-purple-600" />
              </div>
              <h3 className="text-xl font-bold mb-2">Instant Generation</h3>
              <p className="text-gray-600">
                Generate fresh articles on-demand for any topic in seconds
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-blue-600 text-white py-16">
        <div className="container mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">
            Ready to Transform Your UPSC Preparation?
          </h2>
          <p className="text-xl mb-8 opacity-90">
            Join thousands of aspirants learning smarter with AI
          </p>
          <Link href="/generate">
            <Button size="lg" variant="secondary" className="gap-2">
              Start Generating Now
              <Sparkles className="h-5 w-5" />
            </Button>
          </Link>
        </div>
      </section>
    </div>
  );
}

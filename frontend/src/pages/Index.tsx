import React from 'react';

import { Sidebar } from '@/components/Sidebar';
import { MainContent } from '@/components/MainContent';

const Index: React.FC = () => {
  return (
    <div className="min-h-screen bg-background flex w-full relative">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-[60] h-[3px] bg-eagleshot-stripe" />
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content */}
      <MainContent />
    </div>
  );
};

export default Index;

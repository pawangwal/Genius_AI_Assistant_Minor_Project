import React from 'react';
import StarfieldBackground from './components/StarfieldBackground';
import MainInterface from './components/MainInterface';
import NotificationToast from './components/NotificationToast';
import { InterfaceProvider } from './context/InterfaceContext';
import { NotificationProvider } from './context/NotificationContext';

function App() {
  return (
    <NotificationProvider>
      <InterfaceProvider>
        <div className="relative w-full h-screen overflow-hidden bg-black text-white font-['Space_Grotesk']">
          <StarfieldBackground />
          <NotificationToast />
          <MainInterface />
        </div>
      </InterfaceProvider>
    </NotificationProvider>
  );
}

export default App;
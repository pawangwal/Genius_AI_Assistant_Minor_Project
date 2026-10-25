import React from 'react';
import VoiceVisualizer from './VoiceVisualizer';
import CommandConsole from './CommandConsole';
import SystemStatusCards from './SystemStatusCards';
import NavigationSidebar from './NavigationSidebar';
import VoiceActivationButton from './VoiceActivationButton';
import TasksPanel from './panels/TasksPanel';
import RemindersPanel from './panels/RemindersPanel';
import SmartDevicesPanel from './panels/SmartDevicesPanel';
import IPLPredictorPanel from './panels/IPLPredictorPanel';
import SettingsPanel from './panels/SettingsPanel';
import ChatPanel from './panels/ChatPanel';
import CricketScoresPanel from './panels/CricketScoresPanel';
import { useInterface } from '../context/InterfaceContext';

const MainInterface = () => {
  const { isListening, activePanel } = useInterface();

  const renderPanel = () => {
    switch (activePanel) {
      case 'chat':
        return <ChatPanel />;
      case 'cricket':
        return <CricketScoresPanel />;
      case 'tasks':
        return <TasksPanel />;
      case 'reminders':
        return <RemindersPanel />;
      case 'devices':
        return <SmartDevicesPanel />;
      case 'console':
        return <CommandConsole />;
      case 'ipl':
        return <IPLPredictorPanel />;
      case 'settings':
        return <SettingsPanel />;
      default:
        return (
          <>
            <div className="flex-1 flex items-center justify-center w-full min-h-0">
              <VoiceVisualizer isActive={isListening} />
            </div>
            <div className="w-full mt-4">
              <CommandConsole />
            </div>
          </>
        );
    }
  };

  return (
    <div className="relative w-full h-full flex flex-col md:flex-row overflow-hidden">
      <NavigationSidebar />

      <div className="flex-1 flex flex-col h-full p-4 md:p-6 lg:p-8 min-h-0 overflow-hidden">
        <div className="w-full mb-3 shrink-0">
          <SystemStatusCards />
        </div>

        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {renderPanel()}
        </div>

        <div className="md:hidden flex justify-center mt-3 shrink-0">
          <VoiceActivationButton />
        </div>
      </div>
    </div>
  );
};


export default MainInterface;
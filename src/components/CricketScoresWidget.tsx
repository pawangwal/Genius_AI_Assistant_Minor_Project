import React, { useState, useEffect, useRef, useCallback } from 'react';
import { RotateCw, ChevronLeft, ChevronRight, Activity } from 'lucide-react';
import { fetchCricketScores, CricketMatch } from '../services/api';

interface CricketScoresWidgetProps {
  expanded: boolean;
}

const CricketScoresWidget: React.FC<CricketScoresWidgetProps> = ({ expanded }) => {
  const [matches, setMatches] = useState<CricketMatch[]>([]);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'empty' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [currentIndex, setCurrentIndex] = useState(0);
  const isFetchingRef = useRef(false);

  const loadScores = useCallback(async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    setStatus((prev) => (prev === 'idle' ? 'loading' : prev));

    try {
      const resp = await fetchCricketScores();
      if (resp.status === 'success' && resp.matches.length > 0) {
        setMatches(resp.matches);
        setStatus('success');
        setErrorMessage('');
      } else if (resp.status === 'empty' || resp.matches.length === 0) {
        setMatches([]);
        setStatus('empty');
        setErrorMessage(resp.message || 'No live matches currently');
      } else {
        setMatches([]);
        setStatus('error');
        setErrorMessage(resp.message || 'Unable to fetch cricket scores');
      }
    } catch (err: unknown) {
      setMatches([]);
      setStatus('error');
      setErrorMessage(err instanceof Error ? err.message : 'Cricket score service offline');
    } finally {
      isFetchingRef.current = false;
    }
  }, []);

  useEffect(() => {
    loadScores();
    const interval = setInterval(loadScores, 60000); // 60s poll
    return () => clearInterval(interval);
  }, [loadScores]);

  const handlePrev = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev > 0 ? prev - 1 : matches.length - 1));
  };

  const handleNext = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentIndex((prev) => (prev < matches.length - 1 ? prev + 1 : 0));
  };

  const handleRefresh = (e: React.MouseEvent) => {
    e.stopPropagation();
    loadScores();
  };

  if (!expanded) {
    return (
      <div 
        className="my-2 mx-2 p-2 rounded-lg bg-cyan-950/40 border border-cyan-800/40 flex flex-col items-center justify-center cursor-pointer group hover:border-cyan-500/50 transition-all"
        title="Live Cricket Scores"
        onClick={handleRefresh}
      >
        <div className="relative">
          <Activity size={18} className="text-cyan-400 group-hover:text-cyan-300" />
          <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-500" />
        </div>
      </div>
    );
  }

  const currentMatch = matches[currentIndex] || null;

  return (
    <div className="my-2 mx-2 p-2.5 rounded-lg bg-gray-900/80 border border-cyan-900/50 backdrop-blur-sm shadow-md transition-all hover:border-cyan-700/60">
      {/* Header bar */}
      <div className="flex items-center justify-between pb-1.5 border-b border-cyan-900/40 text-[11px]">
        <div className="flex items-center space-x-1.5">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          <span className="font-semibold text-cyan-400 tracking-wide">LIVE SCORES</span>
        </div>

        <div className="flex items-center space-x-1">
          {matches.length > 1 && (
            <div className="flex items-center space-x-0.5 text-gray-400">
              <button 
                onClick={handlePrev} 
                className="p-0.5 hover:text-cyan-300 rounded hover:bg-cyan-900/30"
                title="Previous match"
              >
                <ChevronLeft size={12} />
              </button>
              <span className="text-[10px] text-gray-500">
                {currentIndex + 1}/{matches.length}
              </span>
              <button 
                onClick={handleNext} 
                className="p-0.5 hover:text-cyan-300 rounded hover:bg-cyan-900/30"
                title="Next match"
              >
                <ChevronRight size={12} />
              </button>
            </div>
          )}
          <button
            onClick={handleRefresh}
            className={`p-1 text-gray-400 hover:text-cyan-300 rounded transition-colors ${
              isFetchingRef.current ? 'animate-spin text-cyan-400' : ''
            }`}
            title="Refresh scores"
          >
            <RotateCw size={11} />
          </button>
        </div>
      </div>

      {/* Body content */}
      <div className="pt-1.5 text-[11px]">
        {status === 'loading' && matches.length === 0 ? (
          <div className="flex items-center justify-center py-2 text-gray-400 text-[10px]">
            <RotateCw size={11} className="animate-spin mr-1.5 text-cyan-400" />
            <span>Loading live matches...</span>
          </div>
        ) : status === 'error' && matches.length === 0 ? (
          <div className="py-1 text-center">
            <p className="text-[10px] text-amber-400 leading-tight line-clamp-2">
              {errorMessage || 'API unavailable'}
            </p>
            <button
              onClick={handleRefresh}
              className="mt-1 text-[9px] text-cyan-400 underline hover:text-cyan-300"
            >
              Retry
            </button>
          </div>
        ) : status === 'empty' && matches.length === 0 ? (
          <div className="py-1.5 text-center text-[10px] text-gray-400">
            No live matches right now
          </div>
        ) : currentMatch ? (
          <div>
            <div className="flex items-center justify-between text-gray-200 font-medium">
              <span className="truncate max-w-[130px] text-[11px] font-semibold text-cyan-200">
                {currentMatch.teams.length >= 2
                  ? `${currentMatch.teams[0]} vs ${currentMatch.teams[1]}`
                  : currentMatch.name}
              </span>
              <span className="text-[9px] px-1 py-0.2 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/40">
                {currentMatch.match_type}
              </span>
            </div>

            {/* Inning Scores */}
            <div className="my-1 space-y-0.5">
              {currentMatch.scores.length > 0 ? (
                currentMatch.scores.map((sc, i) => (
                  <div key={i} className="flex justify-between items-center text-[10px] text-gray-300">
                    <span className="truncate max-w-[95px] text-gray-400">{sc.inning || `Inning ${i + 1}`}</span>
                    <span className="font-mono text-cyan-300 font-bold">
                      {sc.runs}/{sc.wickets} <span className="text-[9px] text-gray-400 font-normal">({sc.overs} ov)</span>
                    </span>
                  </div>
                ))
              ) : (
                <div className="text-[10px] text-gray-400 italic">Score not yet underway</div>
              )}
            </div>

            {/* Status note */}
            <p className="text-[9px] text-emerald-400 font-medium truncate pt-0.5 border-t border-cyan-950/60">
              {currentMatch.status || (currentMatch.match_ended ? 'Match Finished' : 'In Progress')}
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default CricketScoresWidget;

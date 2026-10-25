import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  Activity, 
  RotateCw, 
  Search, 
  Filter, 
  MapPin, 
  Calendar, 
  Trophy, 
  CheckCircle2, 
  Clock, 
  AlertCircle 
} from 'lucide-react';
import { fetchAllCricketScores, CricketMatch, CricketScoresResponse } from '../../services/api';

const CricketScoresPanel: React.FC = () => {
  const [matches, setMatches] = useState<CricketMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Filtering states
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'live' | 'finished'>('all');
  const [formatFilter, setFormatFilter] = useState<string>('all');

  const loadScores = useCallback(async (manual = false) => {
    if (manual) setIsRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      const resp: CricketScoresResponse = await fetchAllCricketScores();
      if (resp.status === 'success' && resp.matches) {
        setMatches(resp.matches);
        setError(null);
      } else if (resp.status === 'empty' || (resp.matches && resp.matches.length === 0)) {
        setMatches([]);
        setError(null);
      } else {
        setMatches([]);
        setError(resp.message || 'Unable to retrieve cricket scores from upstream provider.');
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Cricket score service is offline.');
      setMatches([]);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadScores();
    const interval = setInterval(() => loadScores(false), 45000); // 45s auto poll
    return () => clearInterval(interval);
  }, [loadScores]);

  // Unique formats extracted from current matches
  const availableFormats = useMemo(() => {
    const formats = new Set<string>();
    matches.forEach((m) => {
      if (m.match_type) formats.add(m.match_type.toUpperCase());
    });
    return Array.from(formats);
  }, [matches]);

  // Filtered matches
  const filteredMatches = useMemo(() => {
    return matches.filter((m) => {
      // 1. Search Query filter
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesName = m.name.toLowerCase().includes(query);
        const matchesTeam = m.teams.some((t) => t.toLowerCase().includes(query));
        const matchesVenue = m.venue.toLowerCase().includes(query);
        if (!matchesName && !matchesTeam && !matchesVenue) return false;
      }

      // 2. Status filter
      if (statusFilter === 'live' && m.match_ended) return false;
      if (statusFilter === 'finished' && !m.match_ended) return false;

      // 3. Format filter
      if (formatFilter !== 'all' && m.match_type.toUpperCase() !== formatFilter.toUpperCase()) {
        return false;
      }

      return true;
    });
  }, [matches, searchQuery, statusFilter, formatFilter]);

  return (
    <div className="h-full flex flex-col min-h-0 bg-gray-950/60 rounded-xl border border-cyan-900/40 backdrop-blur-md shadow-2xl overflow-hidden">
      {/* Top Header */}
      <div className="p-4 md:p-5 border-b border-cyan-900/40 bg-gray-900/40 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
            <Activity size={22} className="text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-gray-100 tracking-wide">Live Cricket Matches</h1>
              <span className="flex items-center text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-800/50">
                <span className="relative flex h-1.5 w-1.5 mr-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                </span>
                CricAPI Live Stream
              </span>
            </div>
            <p className="text-xs text-gray-400">
              International & domestic fixtures with real-time scorecards and match statuses
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={() => loadScores(true)}
            disabled={isRefreshing || loading}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-950/60 border border-cyan-800/60 hover:bg-cyan-900/40 text-cyan-300 text-xs transition-all disabled:opacity-50"
            title="Refresh latest scores"
          >
            <RotateCw size={13} className={isRefreshing ? 'animate-spin text-cyan-400' : ''} />
            <span>{isRefreshing ? 'Updating...' : 'Refresh'}</span>
          </button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-3 md:px-5 border-b border-cyan-900/30 bg-black/20 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Status Tabs */}
        <div className="flex items-center space-x-1 bg-gray-900/80 p-1 rounded-lg border border-cyan-900/40">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1 rounded-md font-medium transition-all ${
              statusFilter === 'all'
                ? 'bg-cyan-900/80 text-cyan-200 shadow'
                : 'text-gray-400 hover:text-cyan-300'
            }`}
          >
            All Matches ({matches.length})
          </button>
          <button
            onClick={() => setStatusFilter('live')}
            className={`px-3 py-1 rounded-md font-medium transition-all ${
              statusFilter === 'live'
                ? 'bg-emerald-900/80 text-emerald-200 shadow'
                : 'text-gray-400 hover:text-emerald-300'
            }`}
          >
            Live ({matches.filter((m) => !m.match_ended).length})
          </button>
          <button
            onClick={() => setStatusFilter('finished')}
            className={`px-3 py-1 rounded-md font-medium transition-all ${
              statusFilter === 'finished'
                ? 'bg-blue-900/80 text-blue-200 shadow'
                : 'text-gray-400 hover:text-blue-300'
            }`}
          >
            Finished ({matches.filter((m) => m.match_ended).length})
          </button>
        </div>

        {/* Format Filter & Search */}
        <div className="flex items-center space-x-2 flex-1 md:flex-initial justify-end">
          {availableFormats.length > 0 && (
            <div className="flex items-center space-x-1">
              <Filter size={13} className="text-gray-400 ml-1" />
              <select
                value={formatFilter}
                onChange={(e) => setFormatFilter(e.target.value)}
                className="bg-gray-900 border border-cyan-900/50 text-gray-300 rounded-lg px-2.5 py-1 text-xs focus:outline-none focus:border-cyan-500"
              >
                <option value="all">All Formats</option>
                {availableFormats.map((fmt) => (
                  <option key={fmt} value={fmt}>{fmt}</option>
                ))}
              </select>
            </div>
          )}

          <div className="relative flex-1 md:w-56">
            <Search size={13} className="absolute left-2.5 top-2.5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter by team or venue..."
              className="w-full bg-gray-900/90 border border-cyan-900/50 rounded-lg pl-8 pr-3 py-1 text-xs text-gray-200 placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 md:p-5 min-h-0">
        {loading && matches.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400 space-y-3">
            <RotateCw size={28} className="animate-spin text-cyan-400" />
            <p className="text-sm font-medium">Fetching real-time cricket fixtures...</p>
          </div>
        ) : error && matches.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center px-4">
            <div className="w-12 h-12 rounded-full bg-amber-950/60 border border-amber-700/50 flex items-center justify-center mb-3">
              <AlertCircle size={24} className="text-amber-400" />
            </div>
            <h3 className="text-base font-semibold text-gray-200 mb-1">Cricket Scores Unavailable</h3>
            <p className="text-xs text-gray-400 max-w-md mb-4">{error}</p>
            <button
              onClick={() => loadScores(true)}
              className="px-4 py-2 rounded-lg bg-cyan-900/60 hover:bg-cyan-800 text-cyan-200 text-xs font-medium border border-cyan-700/50 transition-colors"
            >
              Retry Connection
            </button>
          </div>
        ) : filteredMatches.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center text-gray-400 space-y-2">
            <Trophy size={32} className="text-gray-600 mb-1" />
            <p className="text-sm font-medium text-gray-300">No matches found</p>
            <p className="text-xs text-gray-500 max-w-sm">
              {searchQuery || statusFilter !== 'all' || formatFilter !== 'all'
                ? 'Try adjusting your search filters or format options.'
                : 'No live matches are currently broadcast in CricAPI.'}
            </p>
            {(searchQuery || statusFilter !== 'all' || formatFilter !== 'all') && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setStatusFilter('all');
                  setFormatFilter('all');
                }}
                className="mt-2 text-xs text-cyan-400 underline hover:text-cyan-300"
              >
                Clear all filters
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredMatches.map((match) => (
              <MatchCard key={match.id} match={match} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

interface MatchCardProps {
  match: CricketMatch;
}

const MatchCard: React.FC<MatchCardProps> = ({ match }) => {
  const isLive = !match.match_ended;

  return (
    <div className="p-4 rounded-xl bg-gray-900/60 border border-cyan-900/40 hover:border-cyan-700/60 transition-all shadow-md flex flex-col justify-between">
      {/* Header Info */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/50 uppercase tracking-wide">
              {match.match_type || 'MATCH'}
            </span>
            {isLive ? (
              <span className="flex items-center text-[10px] px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
                <span className="relative flex h-1.5 w-1.5 mr-1.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
                </span>
                LIVE
              </span>
            ) : (
              <span className="flex items-center text-[10px] px-2 py-0.5 rounded-full bg-gray-800 text-gray-300 border border-gray-700">
                <CheckCircle2 size={10} className="mr-1 text-gray-400" />
                FINISHED
              </span>
            )}
          </div>

          <div className="flex items-center text-[10px] text-gray-400 font-mono">
            <Calendar size={11} className="mr-1 text-gray-500" />
            <span>{match.date || 'Recent'}</span>
          </div>
        </div>

        {/* Match Name / Teams */}
        <h3 className="text-sm font-bold text-gray-100 mb-3 tracking-wide">
          {match.teams.length >= 2 ? (
            <div className="flex items-center space-x-2">
              <span className="text-cyan-300">{match.teams[0]}</span>
              <span className="text-xs text-gray-500 font-normal">vs</span>
              <span className="text-purple-300">{match.teams[1]}</span>
            </div>
          ) : (
            match.name
          )}
        </h3>

        {/* Scorecard Table */}
        <div className="rounded-lg bg-black/40 border border-cyan-900/30 p-2.5 mb-3 space-y-1.5">
          {match.scores && match.scores.length > 0 ? (
            match.scores.map((sc, idx) => (
              <div key={idx} className="flex items-center justify-between text-xs">
                <span className="font-medium text-gray-300 truncate max-w-[170px]">
                  {sc.inning || `Innings ${idx + 1}`}
                </span>
                <div className="font-mono flex items-center space-x-2">
                  <span className="font-bold text-cyan-300 text-sm">
                    {sc.runs}/{sc.wickets}
                  </span>
                  <span className="text-[11px] text-gray-400">
                    ({sc.overs} ov)
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="text-xs text-gray-500 italic py-1 text-center">
              Innings scores not yet available
            </div>
          )}
        </div>
      </div>

      {/* Match Status & Venue Footer */}
      <div className="pt-2.5 border-t border-cyan-900/30 space-y-1 text-xs">
        <div className="flex items-center justify-between">
          <p className={`font-medium ${isLive ? 'text-emerald-400' : 'text-cyan-400'} text-xs truncate max-w-[85%]`}>
            {match.status || (isLive ? 'Match in progress' : 'Match ended')}
          </p>
        </div>

        {match.venue && match.venue !== 'Unknown Venue' && (
          <div className="flex items-center text-[10px] text-gray-400 truncate">
            <MapPin size={10} className="mr-1 text-gray-500 shrink-0" />
            <span className="truncate">{match.venue}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default CricketScoresPanel;

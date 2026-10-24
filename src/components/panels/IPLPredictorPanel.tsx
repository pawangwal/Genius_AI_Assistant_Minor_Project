import React, { useState } from 'react';
import { Trophy, ArrowRight, Loader2, AlertCircle, Activity, Gauge } from 'lucide-react';
import { predictIPLWin, IPLPredictionResponse } from '../../services/api';

interface Team {
  name: string;
  city: string;
  stadium: string;
  captain: string;
}

const teams: Team[] = [
  { name: 'Chennai Super Kings', city: 'Chennai', stadium: 'M. A. Chidambaram Stadium', captain: 'Ruturaj Gaikwad' },
  { name: 'Delhi Capitals', city: 'Delhi', stadium: 'Arun Jaitley Stadium', captain: 'Axar Patel' },
  { name: 'Gujarat Titans', city: 'Ahmedabad', stadium: 'Narendra Modi Stadium', captain: 'Shubman Gill' },
  { name: 'Kolkata Knight Riders', city: 'Kolkata', stadium: 'Eden Gardens', captain: 'Ajinkya Rahane' },
  { name: 'Lucknow Super Giants', city: 'Lucknow', stadium: 'BRSABV Ekana Stadium', captain: 'Rishabh Pant' },
  { name: 'Mumbai Indians', city: 'Mumbai', stadium: 'Wankhede Stadium', captain: 'Hardik Pandya' },
  { name: 'Punjab Kings', city: 'Mohali', stadium: 'Maharaja Yadavindra Singh Stadium', captain: 'Shreyas Iyer' },
  { name: 'Rajasthan Royals', city: 'Jaipur', stadium: 'Sawai Mansingh Stadium', captain: 'Sanju Samson' },
  { name: 'Royal Challengers Bengaluru', city: 'Bengaluru', stadium: 'M. Chinnaswamy Stadium', captain: 'Rajat Patidar' },
  { name: 'Sunrisers Hyderabad', city: 'Hyderabad', stadium: 'Rajiv Gandhi Stadium', captain: 'Pat Cummins' },
];

const IPLPredictorPanel: React.FC = () => {
  const [battingTeam, setBattingTeam] = useState('Chennai Super Kings');
  const [bowlingTeam, setBowlingTeam] = useState('Mumbai Indians');
  const [city, setCity] = useState('Chennai');
  const [targetScore, setTargetScore] = useState<number>(175);
  const [currentScore, setCurrentScore] = useState<number>(115);
  const [oversCompleted, setOversCompleted] = useState<number>(14);
  const [ballsInOver, setBallsInOver] = useState<number>(2);
  const [wicketsOut, setWicketsOut] = useState<number>(3);

  const [prediction, setPrediction] = useState<IPLPredictionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleBattingTeamChange = (value: string) => {
    setBattingTeam(value);
    if (value === bowlingTeam) {
      const alt = teams.find(t => t.name !== value);
      if (alt) setBowlingTeam(alt.name);
    }
  };

  const handleBowlingTeamChange = (value: string) => {
    setBowlingTeam(value);
    if (value === battingTeam) {
      const alt = teams.find(t => t.name !== value);
      if (alt) setBattingTeam(alt.name);
    }
  };

  const handlePredict = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const result = await predictIPLWin({
        batting_team: battingTeam,
        bowling_team: bowlingTeam,
        city: city,
        target_score: Number(targetScore),
        current_score: Number(currentScore),
        overs_completed: Number(oversCompleted),
        balls_in_over: Number(ballsInOver),
        wickets_out: Number(wicketsOut),
      });
      setPrediction(result);
    } catch (err: any) {
      setError(err.message || 'Failed to communicate with prediction service.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col space-y-6 overflow-y-auto pr-1">
      <div className="flex items-center justify-between border-b border-yellow-900/50 pb-4">
        <div className="flex items-center">
          <Trophy className="text-yellow-400 mr-2" size={26} />
          <div>
            <h2 className="text-xl font-bold text-yellow-300">IPL Match Win Predictor</h2>
            <p className="text-xs text-yellow-600">Offline scikit-learn match chase probability inference engine</p>
          </div>
        </div>
        {prediction && (
          <span className="text-xs px-2.5 py-1 rounded bg-yellow-950/80 border border-yellow-800 text-yellow-400 flex items-center gap-1">
            <Activity size={12} />
            Latency: {prediction.inference_latency_ms}ms
          </span>
        )}
      </div>

      <form onSubmit={handlePredict} className="space-y-4">
        {/* Team Selection */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-yellow-400">
              Batting Team (Chasing)
            </label>
            <select
              value={battingTeam}
              onChange={(e) => handleBattingTeamChange(e.target.value)}
              className="w-full bg-black/50 border border-yellow-900/60 rounded-lg px-3 py-2 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            >
              {teams.map((t) => (
                <option key={t.name} value={t.name} disabled={t.name === bowlingTeam}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-yellow-400">
              Bowling Team (Defending)
            </label>
            <select
              value={bowlingTeam}
              onChange={(e) => handleBowlingTeamChange(e.target.value)}
              className="w-full bg-black/50 border border-yellow-900/60 rounded-lg px-3 py-2 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            >
              {teams.map((t) => (
                <option key={t.name} value={t.name} disabled={t.name === battingTeam}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold uppercase tracking-wider text-yellow-400">
              Host City
            </label>
            <select
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="w-full bg-black/50 border border-yellow-900/60 rounded-lg px-3 py-2 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            >
              {teams.map((t) => (
                <option key={t.city} value={t.city}>
                  {t.city} ({t.stadium})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Match State Numbers */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2">
          <div className="space-y-1">
            <label className="text-xs text-yellow-400">Target Score</label>
            <input
              type="number"
              min="1"
              max="400"
              value={targetScore}
              onChange={(e) => setTargetScore(Number(e.target.value))}
              required
              className="w-full bg-black/50 border border-yellow-900/60 rounded px-2.5 py-1.5 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-yellow-400">Current Score</label>
            <input
              type="number"
              min="0"
              max="400"
              value={currentScore}
              onChange={(e) => setCurrentScore(Number(e.target.value))}
              required
              className="w-full bg-black/50 border border-yellow-900/60 rounded px-2.5 py-1.5 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-yellow-400">Overs Completed</label>
            <input
              type="number"
              min="0"
              max="20"
              value={oversCompleted}
              onChange={(e) => setOversCompleted(Number(e.target.value))}
              required
              className="w-full bg-black/50 border border-yellow-900/60 rounded px-2.5 py-1.5 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-yellow-400">Balls in Over</label>
            <input
              type="number"
              min="0"
              max="5"
              value={ballsInOver}
              onChange={(e) => setBallsInOver(Number(e.target.value))}
              required
              className="w-full bg-black/50 border border-yellow-900/60 rounded px-2.5 py-1.5 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs text-yellow-400">Wickets Fallen</label>
            <input
              type="number"
              min="0"
              max="10"
              value={wicketsOut}
              onChange={(e) => setWicketsOut(Number(e.target.value))}
              required
              className="w-full bg-black/50 border border-yellow-900/60 rounded px-2.5 py-1.5 text-yellow-200 text-sm focus:outline-none focus:border-yellow-500"
            />
          </div>
        </div>

        {error && (
          <div className="p-3 bg-red-950/50 border border-red-800 rounded-lg text-red-300 text-sm flex items-center gap-2">
            <AlertCircle size={16} className="text-red-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-gradient-to-r from-yellow-600 via-yellow-500 to-amber-600 hover:from-yellow-500 hover:to-amber-500 text-black font-bold py-2.5 px-4 rounded-lg flex items-center justify-center gap-2 transition-all duration-200 disabled:opacity-50"
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin" size={18} />
              <span>Calculating Win Probabilities...</span>
            </>
          ) : (
            <>
              <Gauge size={18} />
              <span>Predict Win Probability</span>
            </>
          )}
        </button>
      </form>

      {/* Prediction Output Results */}
      {prediction && (
        <div className="p-5 bg-gradient-to-br from-yellow-950/40 via-black/60 to-orange-950/30 rounded-xl border border-yellow-800/60 space-y-5 animate-in fade-in duration-300">
          <div className="flex items-center justify-between border-b border-yellow-900/40 pb-3">
            <div>
              <span className="text-xs uppercase tracking-wider text-yellow-500 font-semibold">Projected Winner</span>
              <h3 className="text-2xl font-black text-yellow-300">{prediction.projected_winner}</h3>
            </div>
            <div className="text-right">
              <span className="text-xs uppercase tracking-wider text-yellow-500 font-semibold">Status</span>
              <p className="text-sm font-medium text-yellow-200">
                {prediction.match_completed ? 'Match Concluded' : 'Chase In Progress'}
              </p>
            </div>
          </div>

          {/* Probability Comparison Bars */}
          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-semibold text-yellow-300">{prediction.batting_team} (Chasing)</span>
                <span className="font-mono font-bold text-yellow-400">
                  {(prediction.batting_win_probability * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-3.5 bg-black/60 rounded-full overflow-hidden border border-yellow-900/60">
                <div
                  className="h-full bg-gradient-to-r from-yellow-500 to-amber-400 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, prediction.batting_win_probability * 100))}%` }}
                />
              </div>
            </div>

            <div>
              <div className="flex justify-between text-sm mb-1">
                <span className="font-semibold text-yellow-300">{prediction.bowling_team} (Defending)</span>
                <span className="font-mono font-bold text-yellow-400">
                  {(prediction.bowling_win_probability * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-3.5 bg-black/60 rounded-full overflow-hidden border border-yellow-900/60">
                <div
                  className="h-full bg-gradient-to-r from-orange-600 to-amber-600 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, prediction.bowling_win_probability * 100))}%` }}
                />
              </div>
            </div>
          </div>

          {/* Derived Features Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5 pt-2">
            <div className="p-2.5 bg-black/40 border border-yellow-900/40 rounded-lg text-center">
              <div className="text-[11px] uppercase tracking-wider text-yellow-500">Runs Needed</div>
              <div className="text-lg font-bold text-yellow-200 font-mono">{prediction.derived_features.runs_left}</div>
            </div>
            <div className="p-2.5 bg-black/40 border border-yellow-900/40 rounded-lg text-center">
              <div className="text-[11px] uppercase tracking-wider text-yellow-500">Balls Left</div>
              <div className="text-lg font-bold text-yellow-200 font-mono">{prediction.derived_features.balls_left}</div>
            </div>
            <div className="p-2.5 bg-black/40 border border-yellow-900/40 rounded-lg text-center">
              <div className="text-[11px] uppercase tracking-wider text-yellow-500">Wickets in Hand</div>
              <div className="text-lg font-bold text-yellow-200 font-mono">{prediction.derived_features.wickets_left}</div>
            </div>
            <div className="p-2.5 bg-black/40 border border-yellow-900/40 rounded-lg text-center">
              <div className="text-[11px] uppercase tracking-wider text-yellow-500">Current RR</div>
              <div className="text-lg font-bold text-yellow-200 font-mono">{prediction.derived_features.crr}</div>
            </div>
            <div className="p-2.5 bg-black/40 border border-yellow-900/40 rounded-lg text-center">
              <div className="text-[11px] uppercase tracking-wider text-yellow-500">Required RR</div>
              <div className="text-lg font-bold text-yellow-200 font-mono">{prediction.derived_features.rrr}</div>
            </div>
          </div>

          <p className="text-xs text-yellow-400/90 italic pt-1 border-t border-yellow-900/30">
            {prediction.status_summary}
          </p>
        </div>
      )}
    </div>
  );
};

export default IPLPredictorPanel;
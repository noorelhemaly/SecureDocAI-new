import { useState, useEffect } from 'react';
import {
  Shield,
  CheckCircle2,
  XCircle,
  Link2,
  Hash,
  Clock,
  Database,
  Cpu,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  Lock,
  Loader2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { getBlockchainAudit, mineBlock, getUsers, type BlockchainAuditResult, type BlockchainBlock, type User } from '../services/api';

// User name lookup helper
const getUserName = (userId: string, users: User[]): string => {
  const user = users.find(u => u.user_id === userId);
  return user ? user.name : userId;
};

interface BlockCardProps {
  block: BlockchainBlock;
  isExpanded: boolean;
  onToggle: () => void;
  users: User[];
}

function BlockCard({ block, isExpanded, onToggle, users }: BlockCardProps) {
  const isGenesis = block.index === 0;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Block Header */}
      <button
        onClick={onToggle}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${isGenesis ? 'bg-purple-100 dark:bg-purple-900/30' : 'bg-blue-100 dark:bg-blue-900/30'}`}>
            {isGenesis ? (
              <Database className={`w-5 h-5 ${isGenesis ? 'text-purple-600 dark:text-purple-400' : 'text-blue-600 dark:text-blue-400'}`} />
            ) : (
              <Link2 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            )}
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                Block #{block.index}
              </span>
              {isGenesis && (
                <span className="px-2 py-0.5 text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded-full">
                  Genesis
                </span>
              )}
              {block.block_signature && (
                <span className="px-2 py-0.5 text-xs bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400 rounded-full">
                  Dilithium3 Signed
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {block.events_count} events{block.block_signature ? ` | Sig: ${block.block_signature.slice(0, 12)}…` : ''}
              {!isGenesis && (() => {
                const classifiedEvents = block.events.filter(e => e.event_type === 'DOCUMENT_CLASSIFIED');
                if (classifiedEvents.length > 0) {
                  const uploaders = [...new Set(classifiedEvents.map(e =>
                    e.data?.user_name ? String(e.data.user_name) : (e.data?.user_id ? getUserName(String(e.data.user_id), users) : null)
                  ).filter(Boolean))];
                  return uploaders.length > 0 ? ` | By: ${uploaders.join(', ')}` : '';
                }
                return '';
              })()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500 dark:text-gray-400 hidden md:block">
            {new Date(block.timestamp).toLocaleString()}
          </span>
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>

      {/* Block Details */}
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-700">
          {/* Hash Information */}
          <div className="mt-4 space-y-3">
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <Hash className="w-4 h-4 text-gray-500" />
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Block Hash</span>
              </div>
              <code className="text-xs text-gray-800 dark:text-gray-200 break-all font-mono">
                {block.hash}
              </code>
            </div>

            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <Link2 className="w-4 h-4 text-gray-500" />
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Previous Hash</span>
              </div>
              <code className="text-xs text-gray-800 dark:text-gray-200 break-all font-mono">
                {block.previous_hash}
              </code>
            </div>

            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <div className="flex items-center gap-2 mb-1">
                <Shield className="w-4 h-4 text-gray-500" />
                <span className="text-xs font-medium text-gray-600 dark:text-gray-400">Merkle Root</span>
              </div>
              <code className="text-xs text-gray-800 dark:text-gray-200 break-all font-mono">
                {block.merkle_root}
              </code>
            </div>
          </div>

          {/* Events in Block */}
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Events in Block
            </h4>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {block.events.map((event, idx) => (
                <div
                  key={event.event_id || idx}
                  className="p-2 bg-gray-50 dark:bg-gray-700/30 rounded-lg text-xs"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className={`px-2 py-0.5 rounded-full font-medium ${
                      event.event_type === 'GENESIS' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' :
                      event.event_type.includes('DENIED') ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                      event.event_type.includes('CLASSIFICATION') ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                      event.event_type.includes('ENCRYPT') ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                      'bg-gray-100 text-gray-700 dark:bg-gray-600 dark:text-gray-300'
                    }`}>
                      {event.event_type}
                    </span>
                    <span className="text-gray-500 dark:text-gray-400">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  {event.data && (
                    <div className="text-gray-600 dark:text-gray-400 mt-1 space-y-0.5">
                      {(event.data.user_id || event.data.user_name) && (
                        <div className="flex items-center gap-1 flex-wrap">
                          <span className="font-medium">
                            {event.event_type === 'DOCUMENT_CLASSIFIED' ? 'Uploaded by:' : 'User:'}
                          </span>
                          <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded font-semibold">
                            {event.data.user_name
                              ? String(event.data.user_name)
                              : getUserName(String(event.data.user_id), users)}
                          </span>
                          {event.data.user_id && event.data.user_id !== 'anonymous' && (
                            <span className="text-gray-500">({String(event.data.user_id)})</span>
                          )}
                          {event.data.user_level && (
                            <span className="px-1.5 py-0.5 bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-300 rounded">
                              Level {String(event.data.user_level)}
                            </span>
                          )}
                        </div>
                      )}
                      {event.data.document_id && (
                        <div><span className="font-medium">Document:</span> {String(event.data.document_id)}</div>
                      )}
                      {event.data.classification && (
                        <div><span className="font-medium">Classification:</span> {String(event.data.classification)}</div>
                      )}
                      {event.data.method && (
                        <div><span className="font-medium">Method:</span> {String(event.data.method)}</div>
                      )}
                      {event.data.action && (
                        <div><span className="font-medium">Action:</span> {String(event.data.action)}</div>
                      )}
                      {event.data.reason && (
                        <div className="text-red-600 dark:text-red-400">
                          <span className="font-medium">Reason:</span> {String(event.data.reason)}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function AuditTrailView() {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [auditData, setAuditData] = useState<BlockchainAuditResult | null>(null);
  const [expandedBlocks, setExpandedBlocks] = useState<Set<number>>(new Set([0]));
  const [mining, setMining] = useState(false);
  const [allUsers, setAllUsers] = useState<User[]>([]);

  const fetchAuditData = async () => {
    if (!user) return;

    try {
      setLoading(true);
      setError(null);
      const [data, usersData] = await Promise.all([
        getBlockchainAudit(user.user_id),
        getUsers()
      ]);
      setAuditData(data);
      setAllUsers(usersData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit trail');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditData();
  }, [user]);

  const handleMineBlock = async () => {
    if (!user) return;

    try {
      setMining(true);
      await mineBlock(user.user_id);
      await fetchAuditData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to mine block');
    } finally {
      setMining(false);
    }
  };

  const toggleBlock = (index: number) => {
    const newExpanded = new Set(expandedBlocks);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedBlocks(newExpanded);
  };

  // Access check
  if (!user || user.access_level < 5) {
    return (
      <div className="p-8">
        <div className="max-w-2xl mx-auto bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-8 text-center">
          <Lock className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-red-700 dark:text-red-400 mb-2">
            Access Denied
          </h2>
          <p className="text-red-600 dark:text-red-300">
            The Blockchain Audit Trail is only accessible to Level 5 Administrators.
          </p>
          <p className="text-sm text-red-500 dark:text-red-400 mt-2">
            Your current access level: {user?.access_level || 0}
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading blockchain audit trail...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="max-w-2xl mx-auto bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl p-8 text-center">
          <AlertTriangle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-red-700 dark:text-red-400 mb-2">
            Error Loading Audit Trail
          </h2>
          <p className="text-red-600 dark:text-red-300">{error}</p>
          <button
            onClick={fetchAuditData}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const status = auditData?.blockchain.status;
  const verification = auditData?.blockchain.verification;
  const blocks = auditData?.blockchain.blocks || [];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-gradient-to-br from-[#1E3A8A] to-[#0891B2] p-3 rounded-xl">
              <Link2 className="w-8 h-8 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                Blockchain Audit Trail
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Immutable, tamper-proof record of all system events
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleMineBlock}
              disabled={mining || (status?.pending_events === 0)}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {mining ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Cpu className="w-4 h-4" />
              )}
              Mine Block
              {status && status.pending_events > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-white/20 rounded">
                  {status.pending_events} pending
                </span>
              )}
            </button>
            <button
              onClick={fetchAuditData}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {/* Chain Status */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-3">
            {verification?.valid ? (
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <CheckCircle2 className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
            ) : (
              <div className="p-2 bg-red-100 dark:bg-red-900/30 rounded-lg">
                <XCircle className="w-6 h-6 text-red-600 dark:text-red-400" />
              </div>
            )}
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Chain Status</p>
              <p className={`text-lg font-semibold ${verification?.valid ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                {verification?.valid ? 'Valid' : 'Compromised'}
              </p>
            </div>
          </div>
        </div>

        {/* Total Blocks */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <Database className="w-6 h-6 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Blocks</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {status?.chain_length || 0}
              </p>
            </div>
          </div>
        </div>

        {/* Total Events */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <Shield className="w-6 h-6 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Events</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                {status?.total_events || 0}
              </p>
            </div>
          </div>
        </div>

        {/* Consensus */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
              <Cpu className="w-6 h-6 text-orange-600 dark:text-orange-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Consensus</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Dilithium3 Signed
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Algorithm Info */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 rounded-xl border border-blue-200 dark:border-blue-800 p-4 mb-6">
        <div className="flex items-start gap-3">
          <Shield className="w-5 h-5 text-blue-600 dark:text-blue-400 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-800 dark:text-blue-300">Blockchain Security</h3>
            <p className="text-sm text-blue-700 dark:text-blue-400 mt-1">
              <strong>Algorithm:</strong> {status?.algorithm} &nbsp;·&nbsp;
              <strong>Block Auth:</strong> {status?.consensus}
            </p>
            <p className="text-xs text-blue-600 dark:text-blue-500 mt-1">
              Each block is cryptographically linked to the previous block via SHA-256 hash chaining.
              Events are secured with a Merkle tree. Each sealed block is signed with CRYSTALS-Dilithium3
              (NIST FIPS 204) — only the server's private key can produce a valid signature, making
              retroactive block forgery impossible even with quantum hardware.
            </p>
          </div>
        </div>
      </div>

      {/* Blockchain Blocks */}
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
          Blockchain ({blocks.length} blocks)
        </h2>

        {/* Chain Visualization */}
        <div className="space-y-3">
          {blocks.slice().reverse().map((block) => (
            <BlockCard
              key={block.index}
              block={block}
              isExpanded={expandedBlocks.has(block.index)}
              onToggle={() => toggleBlock(block.index)}
              users={allUsers}
            />
          ))}
        </div>
      </div>

      {/* Last Block Info */}
      {status?.last_block_hash && (
        <div className="mt-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Latest Block</span>
          </div>
          <div className="text-xs text-gray-600 dark:text-gray-400">
            <p><strong>Hash:</strong> <code className="font-mono">{status.last_block_hash}</code></p>
            <p><strong>Time:</strong> {status.last_block_time ? new Date(status.last_block_time).toLocaleString() : 'N/A'}</p>
          </div>
        </div>
      )}
    </div>
  );
}

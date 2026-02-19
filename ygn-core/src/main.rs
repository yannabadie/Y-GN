use clap::{Parser, Subcommand};

use ygn_core::config;
use ygn_core::gateway;
use ygn_core::hardware;
use ygn_core::mcp;
use ygn_core::provider::{self, Provider};
use ygn_core::registry::{self, NodeRegistry};
use ygn_core::tool;

#[derive(Parser)]
#[command(name = "ygn-core", version, about = "Y-GN data-plane runtime")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Show node status
    Status,
    /// Start the HTTP gateway
    Gateway {
        #[arg(short, long, default_value = "0.0.0.0:3000")]
        bind: String,
    },
    /// Export config JSON schema
    Config {
        #[command(subcommand)]
        action: ConfigAction,
    },
    /// Tool management
    Tools {
        #[command(subcommand)]
        action: ToolsAction,
    },
    /// Provider management
    Providers {
        #[command(subcommand)]
        action: ProvidersAction,
    },
    /// Start MCP server over stdio (JSON-RPC 2.0, newline-delimited)
    Mcp,
    /// Node registry management
    Registry {
        #[command(subcommand)]
        action: RegistryAction,
    },
}

#[derive(Subcommand)]
enum ConfigAction {
    /// Print JSON schema for configuration
    Schema,
}

#[derive(Subcommand)]
enum ToolsAction {
    /// List all registered tools
    List,
}

#[derive(Subcommand)]
enum ProvidersAction {
    /// List all registered providers
    List,
}

#[derive(Subcommand)]
enum RegistryAction {
    /// List all registered nodes
    List,
    /// Show this node's info
    SelfInfo,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "ygn_core=info".into()),
        )
        .init();

    let cli = Cli::parse();

    match cli.command {
        Commands::Status => {
            let cfg = config::NodeConfig::load_or_default();
            println!("ygn-core status: OK");
            println!("  node_role: {}", cfg.node_role);
            println!("  trust_tier: {}", cfg.trust_tier);
        }
        Commands::Gateway { bind } => {
            gateway::run(&bind).await?;
        }
        Commands::Config { action } => match action {
            ConfigAction::Schema => {
                let schema = config::NodeConfig::json_schema();
                println!("{schema}");
            }
        },
        Commands::Tools { action } => match action {
            ToolsAction::List => {
                let mut tool_registry = tool::ToolRegistry::new();
                tool_registry.register(Box::new(tool::EchoTool));
                tool_registry.register(Box::new(hardware::HardwareTool::new()));

                let specs = tool_registry.list();
                println!("Registered tools ({}):", specs.len());
                for spec in &specs {
                    println!("  - {} : {}", spec.name, spec.description);
                }
            }
        },
        Commands::Providers { action } => match action {
            ProvidersAction::List => {
                let stub = provider::StubProvider::default();
                let caps = stub.capabilities();
                println!("Registered providers:");
                println!(
                    "  - {} (tool_calling={}, vision={}, streaming={})",
                    stub.name(),
                    caps.native_tool_calling,
                    caps.vision,
                    caps.streaming
                );
            }
        },
        Commands::Mcp => {
            let server = mcp::McpServer::with_default_tools();
            server.run_stdio()?;
        }
        Commands::Registry { action } => match action {
            RegistryAction::List => {
                let node_registry = registry::InMemoryRegistry::new();
                let all = node_registry
                    .discover(registry::DiscoveryFilter::default())
                    .await?;
                println!("Registered nodes ({}):", all.len());
                for node in &all {
                    println!(
                        "  - {} role={} trust={} endpoints={} caps={:?}",
                        node.node_id,
                        node.role,
                        node.trust_tier,
                        node.endpoints.len(),
                        node.capabilities
                    );
                }
            }
            RegistryAction::SelfInfo => {
                let cfg = config::NodeConfig::load_or_default();
                let node_id = uuid::Uuid::new_v4().to_string();
                let role = match cfg.node_role.as_str() {
                    "brain" => registry::NodeRole::Brain,
                    "core" => registry::NodeRole::Core,
                    "brain-proxy" => registry::NodeRole::BrainProxy,
                    _ => registry::NodeRole::Edge,
                };
                let trust = match cfg.trust_tier.as_str() {
                    "untrusted" => registry::TrustTier::Untrusted,
                    _ => registry::TrustTier::Trusted,
                };
                let info = registry::NodeInfo {
                    node_id,
                    role,
                    endpoints: vec![registry::Endpoint {
                        protocol: "http".to_string(),
                        address: cfg.gateway_bind.clone(),
                    }],
                    trust_tier: trust,
                    capabilities: vec!["echo".to_string(), "hardware".to_string()],
                    last_seen: chrono::Utc::now(),
                    metadata: serde_json::json!({
                        "version": env!("CARGO_PKG_VERSION"),
                    }),
                };
                println!("{}", serde_json::to_string_pretty(&info)?);
            }
        },
    }

    Ok(())
}

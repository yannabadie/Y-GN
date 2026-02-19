use clap::{Parser, Subcommand};

mod config;
mod gateway;

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
}

#[derive(Subcommand)]
enum ConfigAction {
    /// Print JSON schema for configuration
    Schema,
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
    }

    Ok(())
}

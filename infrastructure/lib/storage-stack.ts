import * as cdk from "aws-cdk-lib";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import { Construct } from "constructs";

/**
 * StorageStack — Day 2
 *
 * Creates all DynamoDB tables (with GSIs) and S3 buckets
 * required by the AETHER system.
 */
export class StorageStack extends cdk.Stack {
  // Expose table references for other stacks
  public readonly eventsTable: dynamodb.Table;
  public readonly timelineTable: dynamodb.Table;
  public readonly residentsTable: dynamodb.Table;
  public readonly consentTable: dynamodb.Table;
  public readonly clinicOpsTable: dynamodb.Table;

  public readonly evidenceBucket: s3.Bucket;
  public readonly modelsBucket: s3.Bucket;
  public readonly knowledgeBucket: s3.Bucket;
  public readonly archiveBucket: s3.Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================
    //  DynamoDB Tables
    // =========================================================

    // 1. Events Table — aether-events
    this.eventsTable = new dynamodb.Table(this, "EventsTable", {
      tableName: "aether-events",
      partitionKey: { name: "home_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.NUMBER },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // MVP — easy cleanup
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
      timeToLiveAttribute: "ttl",
    });

    // GSI: event-type-index
    this.eventsTable.addGlobalSecondaryIndex({
      indexName: "event-type-index",
      partitionKey: { name: "event_type", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI: resident-index
    this.eventsTable.addGlobalSecondaryIndex({
      indexName: "resident-index",
      partitionKey: { name: "resident_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // GSI: severity-index
    this.eventsTable.addGlobalSecondaryIndex({
      indexName: "severity-index",
      partitionKey: { name: "severity", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // 2. Timeline Table — aether-timeline
    this.timelineTable = new dynamodb.Table(this, "TimelineTable", {
      tableName: "aether-timeline",
      partitionKey: { name: "home_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "date", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // 3. Residents Table — aether-residents
    this.residentsTable = new dynamodb.Table(this, "ResidentsTable", {
      tableName: "aether-residents",
      partitionKey: { name: "resident_id", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // GSI: home-index on residents
    this.residentsTable.addGlobalSecondaryIndex({
      indexName: "home-index",
      partitionKey: { name: "home_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "resident_id", type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // 4. Consent Ledger Table — aether-consent
    this.consentTable = new dynamodb.Table(this, "ConsentTable", {
      tableName: "aether-consent",
      partitionKey: { name: "resident_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.NUMBER },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true },
    });

    // 5. Clinic Operations Table — aether-clinic-ops
    this.clinicOpsTable = new dynamodb.Table(this, "ClinicOpsTable", {
      tableName: "aether-clinic-ops",
      partitionKey: { name: "clinic_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.NUMBER },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // GSI: home-index on clinic-ops
    this.clinicOpsTable.addGlobalSecondaryIndex({
      indexName: "home-index",
      partitionKey: { name: "home_id", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "timestamp", type: dynamodb.AttributeType.NUMBER },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // =========================================================
    //  S3 Buckets
    // =========================================================

    // 1. Evidence Packets Bucket
    this.evidenceBucket = new s3.Bucket(this, "EvidenceBucket", {
      bucketName: `aether-evidence-${cdk.Aws.REGION}-${cdk.Aws.ACCOUNT_ID}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true, // MVP convenience
      lifecycleRules: [
        {
          id: "transition-to-glacier",
          transitions: [
            {
              storageClass: s3.StorageClass.GLACIER,
              transitionAfter: cdk.Duration.days(30),
            },
          ],
        },
        {
          id: "delete-old-evidence",
          expiration: cdk.Duration.days(2555), // 7 years for compliance
        },
      ],
    });

    // 2. Model Artifacts Bucket
    this.modelsBucket = new s3.Bucket(this, "ModelsBucket", {
      bucketName: `aether-models-${cdk.Aws.REGION}-${cdk.Aws.ACCOUNT_ID}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        {
          id: "delete-old-versions",
          noncurrentVersionExpiration: cdk.Duration.days(90),
        },
      ],
    });

    // 3. Knowledge Packs Bucket
    this.knowledgeBucket = new s3.Bucket(this, "KnowledgeBucket", {
      bucketName: `aether-knowledge-${cdk.Aws.REGION}-${cdk.Aws.ACCOUNT_ID}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // 4. Archive Bucket
    this.archiveBucket = new s3.Bucket(this, "ArchiveBucket", {
      bucketName: `aether-archive-${cdk.Aws.REGION}-${cdk.Aws.ACCOUNT_ID}`,
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    // =========================================================
    //  Outputs
    // =========================================================
    new cdk.CfnOutput(this, "EventsTableName", { value: this.eventsTable.tableName });
    new cdk.CfnOutput(this, "TimelineTableName", { value: this.timelineTable.tableName });
    new cdk.CfnOutput(this, "ResidentsTableName", { value: this.residentsTable.tableName });
    new cdk.CfnOutput(this, "ConsentTableName", { value: this.consentTable.tableName });
    new cdk.CfnOutput(this, "ClinicOpsTableName", { value: this.clinicOpsTable.tableName });
    new cdk.CfnOutput(this, "EvidenceBucketName", { value: this.evidenceBucket.bucketName });
    new cdk.CfnOutput(this, "ModelsBucketName", { value: this.modelsBucket.bucketName });
    new cdk.CfnOutput(this, "KnowledgeBucketName", { value: this.knowledgeBucket.bucketName });
    new cdk.CfnOutput(this, "ArchiveBucketName", { value: this.archiveBucket.bucketName });
  }
}

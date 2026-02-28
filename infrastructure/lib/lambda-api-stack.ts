import * as cdk from "aws-cdk-lib";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as iam from "aws-cdk-lib/aws-iam";
import * as sns from "aws-cdk-lib/aws-sns";
import * as sfn from "aws-cdk-lib/aws-stepfunctions";
import * as logs from "aws-cdk-lib/aws-logs";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as path from "path";
import { Construct } from "constructs";

/**
 * Props passed from StorageStack — DynamoDB tables + S3 buckets.
 */
export interface LambdaApiStackProps extends cdk.StackProps {
  eventsTable: dynamodb.Table;
  timelineTable: dynamodb.Table;
  residentsTable: dynamodb.Table;
  consentTable: dynamodb.Table;
  clinicOpsTable: dynamodb.Table;
  evidenceBucket: s3.Bucket;
  modelsBucket: s3.Bucket;
  userPool: cognito.UserPool;
}

/**
 * LambdaApiStack — Day 4-5
 *
 * Creates all Lambda functions, API Gateway REST API,
 * Step Functions state machines, SNS topic, and necessary IAM permissions.
 */
export class LambdaApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;
  public readonly alertsTopic: sns.Topic;

  public readonly eventProcessorFn: lambda.Function;
  public readonly escalationHandlerFn: lambda.Function;
  public readonly timelineAggregatorFn: lambda.Function;
  public readonly careNavigationFn: lambda.Function;
  public readonly apiHandlerFn: lambda.Function;

  public readonly fallDetectionWorkflow: sfn.StateMachine;
  public readonly medicationAdherenceWorkflow: sfn.StateMachine;

  constructor(scope: Construct, id: string, props: LambdaApiStackProps) {
    super(scope, id, props);

    const {
      eventsTable,
      timelineTable,
      residentsTable,
      consentTable,
      clinicOpsTable,
      evidenceBucket,
      modelsBucket,
      userPool,
    } = props;

    // =========================================================
    //  Cognito Authorizer for API Gateway
    // =========================================================

    const cognitoAuthorizer = new apigateway.CognitoUserPoolsAuthorizer(
      this,
      "AetherAuthorizer",
      {
        cognitoUserPools: [userPool],
        authorizerName: "AetherCognitoAuthorizer",
        identitySource: "method.request.header.Authorization",
      }
    );

    // =========================================================
    //  SNS Topic — Alert Notifications
    // =========================================================

    this.alertsTopic = new sns.Topic(this, "AlertsTopic", {
      topicName: "aether-alerts",
      displayName: "AETHER Alert Notifications",
    });

    // =========================================================
    //  Lambda Layer — Shared Code
    // =========================================================

    const sharedLayer = new lambda.LayerVersion(this, "SharedLayer", {
      layerVersionName: "aether-shared",
      description: "Shared models and utilities for AETHER Lambda functions",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/shared_layer")
      ),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // =========================================================
    //  Common Environment Variables
    // =========================================================

    const commonEnv: Record<string, string> = {
      EVENTS_TABLE: eventsTable.tableName,
      TIMELINE_TABLE: timelineTable.tableName,
      RESIDENTS_TABLE: residentsTable.tableName,
      CONSENT_TABLE: consentTable.tableName,
      CLINIC_OPS_TABLE: clinicOpsTable.tableName,
      EVIDENCE_BUCKET: evidenceBucket.bucketName,
      MODELS_BUCKET: modelsBucket.bucketName,
      SNS_TOPIC_ARN: this.alertsTopic.topicArn,
      POWERTOOLS_SERVICE_NAME: "aether",
      LOG_LEVEL: "INFO",
    };

    // =========================================================
    //  Lambda Functions
    // =========================================================

    // 1. Event Processor
    this.eventProcessorFn = new lambda.Function(this, "EventProcessor", {
      functionName: "aether-event-processor",
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/event_processor")
      ),
      layers: [sharedLayer],
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: { ...commonEnv },
      logRetention: logs.RetentionDays.TWO_WEEKS,
    });

    // 2. Escalation Handler
    this.escalationHandlerFn = new lambda.Function(this, "EscalationHandler", {
      functionName: "aether-escalation-handler",
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/escalation_handler")
      ),
      layers: [sharedLayer],
      memorySize: 256,
      timeout: cdk.Duration.seconds(60),
      environment: { ...commonEnv },
      logRetention: logs.RetentionDays.TWO_WEEKS,
    });

    // 3. Timeline Aggregator
    this.timelineAggregatorFn = new lambda.Function(
      this,
      "TimelineAggregator",
      {
        functionName: "aether-timeline-aggregator",
        runtime: lambda.Runtime.PYTHON_3_11,
        handler: "handler.handler",
        code: lambda.Code.fromAsset(
          path.join(__dirname, "../../cloud/lambdas/timeline_aggregator")
        ),
        layers: [sharedLayer],
        memorySize: 1024,
        timeout: cdk.Duration.seconds(120),
        environment: { ...commonEnv },
        logRetention: logs.RetentionDays.TWO_WEEKS,
      }
    );

    // 4. Care Navigation
    this.careNavigationFn = new lambda.Function(this, "CareNavigation", {
      functionName: "aether-care-navigation",
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/care_navigation")
      ),
      layers: [sharedLayer],
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: { ...commonEnv },
      logRetention: logs.RetentionDays.TWO_WEEKS,
    });

    // 5. API Handler
    this.apiHandlerFn = new lambda.Function(this, "ApiHandler", {
      functionName: "aether-api-handler",
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/api_handler")
      ),
      layers: [sharedLayer],
      memorySize: 512,
      timeout: cdk.Duration.seconds(30),
      environment: { ...commonEnv },
      logRetention: logs.RetentionDays.TWO_WEEKS,
    });

    // 6. Voice Processor
    const voiceProcessorFn = new lambda.Function(this, "VoiceProcessor", {
      functionName: "aether-voice-processor",
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/voice_processor")
      ),
      layers: [sharedLayer],
      memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
      environment: {
        ...commonEnv,
        TRANSCRIBE_LANGUAGE_CODE: "en-IN",
        POLLY_VOICE_ID: "Kajal",
        POLLY_ENGINE: "neural",
        BEDROCK_MODEL_ID: "apac.amazon.nova-lite-v1:0",
      },
      logRetention: logs.RetentionDays.TWO_WEEKS,
    });

    // 7. Documentation Generator
    const docGeneratorFn = new lambda.Function(this, "DocGenerator", {
      functionName: "aether-doc-generator",
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/doc_generator")
      ),
      layers: [sharedLayer],
      memorySize: 1024,
      timeout: cdk.Duration.seconds(300),
      environment: {
        ...commonEnv,
        BEDROCK_MODEL_ID: "apac.amazon.nova-lite-v1:0",
      },
      logRetention: logs.RetentionDays.TWO_WEEKS,
    });

    // 8. Analytics Processor
    const analyticsProcessorFn = new lambda.Function(this, "AnalyticsProcessor", {
      functionName: "aether-analytics-processor",
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: "handler.handler",
      code: lambda.Code.fromAsset(
        path.join(__dirname, "../../cloud/lambdas/analytics_processor")
      ),
      layers: [sharedLayer],
      memorySize: 2048,
      timeout: cdk.Duration.seconds(300),
      environment: { ...commonEnv },
      logRetention: logs.RetentionDays.TWO_WEEKS,
    });

    // =========================================================
    //  Step Functions State Machines
    // =========================================================

    // IAM Role for Step Functions
    const sfnRole = new iam.Role(this, "StepFunctionsRole", {
      roleName: "AetherStepFunctionsRole",
      assumedBy: new iam.ServicePrincipal("states.amazonaws.com"),
    });

    // Grant Step Functions the ability to invoke all AETHER Lambda functions
    // Using a pattern-based policy to avoid circular dependency with Lambda ↔ SFN
    sfnRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["lambda:InvokeFunction"],
        resources: [
          `arn:aws:lambda:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:function:aether-*`,
        ],
      })
    );

    // Grant SNS publish for escalation notifications
    sfnRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["sns:Publish"],
        resources: [this.alertsTopic.topicArn],
      })
    );

    // Fall Detection Workflow
    const fallDefinitionBody = this.loadStepFunctionDefinition(
      path.join(__dirname, "../../cloud/step_functions/fall_detection.asl.json")
    );

    this.fallDetectionWorkflow = new sfn.StateMachine(
      this,
      "FallDetectionWorkflow",
      {
        stateMachineName: "aether-fall-detection",
        definitionBody: sfn.DefinitionBody.fromString(fallDefinitionBody),
        role: sfnRole,
        tracingEnabled: true,
        logs: {
          destination: new logs.LogGroup(this, "FallDetectionLogs", {
            logGroupName: "/aether/stepfunctions/fall-detection",
            retention: logs.RetentionDays.TWO_WEEKS,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
          }),
          level: sfn.LogLevel.ERROR,
        },
      }
    );

    // Medication Adherence Workflow
    const medDefinitionBody = this.loadStepFunctionDefinition(
      path.join(
        __dirname,
        "../../cloud/step_functions/medication_adherence.asl.json"
      )
    );

    this.medicationAdherenceWorkflow = new sfn.StateMachine(
      this,
      "MedicationAdherenceWorkflow",
      {
        stateMachineName: "aether-medication-adherence",
        definitionBody: sfn.DefinitionBody.fromString(medDefinitionBody),
        role: sfnRole,
        tracingEnabled: true,
        logs: {
          destination: new logs.LogGroup(this, "MedicationAdherenceLogs", {
            logGroupName: "/aether/stepfunctions/medication-adherence",
            retention: logs.RetentionDays.TWO_WEEKS,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
          }),
          level: sfn.LogLevel.ERROR,
        },
      }
    );

    // Add workflow ARNs to Lambda environment variables
    // Using constructed ARNs (not token refs) to break circular dependency
    const fallWorkflowArn = `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:aether-fall-detection`;
    const medWorkflowArn = `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:aether-medication-adherence`;

    for (const fn of [
      this.eventProcessorFn,
      this.escalationHandlerFn,
      this.timelineAggregatorFn,
      this.careNavigationFn,
      this.apiHandlerFn,
    ]) {
      fn.addEnvironment("FALL_WORKFLOW_ARN", fallWorkflowArn);
      fn.addEnvironment("MEDICATION_WORKFLOW_ARN", medWorkflowArn);
    }

    // =========================================================
    //  IAM Permissions
    // =========================================================

    const allFunctions = [
      this.eventProcessorFn,
      this.escalationHandlerFn,
      this.timelineAggregatorFn,
      this.careNavigationFn,
      this.apiHandlerFn,
      voiceProcessorFn,
      docGeneratorFn,
      analyticsProcessorFn,
    ];

    for (const fn of allFunctions) {
      // DynamoDB read/write
      eventsTable.grantReadWriteData(fn);
      timelineTable.grantReadWriteData(fn);
      residentsTable.grantReadWriteData(fn);
      consentTable.grantReadWriteData(fn);
      clinicOpsTable.grantReadWriteData(fn);

      // S3 read/write
      evidenceBucket.grantReadWrite(fn);
      modelsBucket.grantReadWrite(fn);

      // SNS publish
      this.alertsTopic.grantPublish(fn);

      // Bedrock invoke access
      fn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            "bedrock:InvokeModel",
            "bedrock:InvokeModelWithResponseStream",
            "bedrock:ApplyGuardrail",
          ],
          resources: ["*"],
        })
      );

      // Transcribe access
      fn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            "transcribe:StartStreamTranscription",
            "transcribe:StartTranscriptionJob",
            "transcribe:GetTranscriptionJob",
          ],
          resources: ["*"],
        })
      );

      // Polly access
      fn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            "polly:SynthesizeSpeech",
            "polly:DescribeVoices",
          ],
          resources: ["*"],
        })
      );

      // Comprehend for sentiment/entity analysis
      fn.addToRolePolicy(
        new iam.PolicyStatement({
          actions: [
            "comprehend:DetectSentiment",
            "comprehend:DetectEntities",
            "comprehend:DetectKeyPhrases",
          ],
          resources: ["*"],
        })
      );
    }

    // Event processor can start Step Functions executions
    // Using pattern-based policy to avoid circular dependency
    this.eventProcessorFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["states:StartExecution"],
        resources: [
          `arn:aws:states:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:stateMachine:aether-*`,
        ],
      })
    );

    // =========================================================
    //  API Gateway — REST API
    // =========================================================

    this.api = new apigateway.RestApi(this, "AetherAPI", {
      restApiName: "AetherAPI",
      description: "AETHER Assisted-Living REST API",
      deployOptions: {
        stageName: "v1",
        tracingEnabled: true,
        metricsEnabled: true,
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          "Content-Type",
          "X-Amz-Date",
          "Authorization",
          "X-Api-Key",
          "X-Amz-Security-Token",
        ],
      },
    });

    const apiIntegration = new apigateway.LambdaIntegration(this.apiHandlerFn);
    const voiceIntegration = new apigateway.LambdaIntegration(voiceProcessorFn);
    const docIntegration = new apigateway.LambdaIntegration(docGeneratorFn);
    const analyticsIntegration = new apigateway.LambdaIntegration(analyticsProcessorFn);

    const authMethodOptions: apigateway.MethodOptions = {
      authorizer: cognitoAuthorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    };

    // /api resource
    const apiResource = this.api.root.addResource("api");

    // GET /api/dashboard
    const dashboard = apiResource.addResource("dashboard");
    dashboard.addMethod("GET", apiIntegration, authMethodOptions);

    // GET|POST /api/events
    const events = apiResource.addResource("events");
    events.addMethod("GET", apiIntegration, authMethodOptions);
    events.addMethod("POST", apiIntegration); // Edge gateway uses API key

    // GET /api/timeline/{home_id}
    const timeline = apiResource.addResource("timeline");
    const timelineHome = timeline.addResource("{home_id}");
    timelineHome.addMethod("GET", apiIntegration, authMethodOptions);

    // GET|PUT /api/residents/{resident_id}
    const residents = apiResource.addResource("residents");
    const residentById = residents.addResource("{resident_id}");
    residentById.addMethod("GET", apiIntegration, authMethodOptions);
    residentById.addMethod("PUT", apiIntegration, authMethodOptions);

    // POST /api/alerts/acknowledge
    const alerts = apiResource.addResource("alerts");
    const acknowledge = alerts.addResource("acknowledge");
    acknowledge.addMethod("POST", apiIntegration, authMethodOptions);

    // GET /api/analytics
    const analytics = apiResource.addResource("analytics");
    analytics.addMethod("GET", analyticsIntegration, authMethodOptions);

    // GET /api/evidence/{packet_id}
    const evidence = apiResource.addResource("evidence");
    const evidenceById = evidence.addResource("{packet_id}");
    evidenceById.addMethod("GET", apiIntegration, authMethodOptions);

    // POST /api/care-navigation/query
    const careNavigation = apiResource.addResource("care-navigation");
    const careNavigationQuery = careNavigation.addResource("query");
    careNavigationQuery.addMethod("POST", apiIntegration, authMethodOptions);

    // POST /api/voice/process — Voice command processing
    const voice = apiResource.addResource("voice");
    const voiceProcess = voice.addResource("process");
    voiceProcess.addMethod("POST", voiceIntegration, authMethodOptions);

    // POST /api/voice/synthesize — TTS synthesis
    const voiceSynthesize = voice.addResource("synthesize");
    voiceSynthesize.addMethod("POST", voiceIntegration, authMethodOptions);

    // POST /api/voice/checkin — Daily check-in
    const voiceCheckin = voice.addResource("checkin");
    voiceCheckin.addMethod("POST", voiceIntegration, authMethodOptions);

    // POST /api/docs/generate — Generate SOAP notes
    const docs = apiResource.addResource("docs");
    const docsGenerate = docs.addResource("generate");
    docsGenerate.addMethod("POST", docIntegration, authMethodOptions);

    // GET /api/docs/{doc_id} — Get generated document
    const docById = docs.addResource("{doc_id}");
    docById.addMethod("GET", docIntegration, authMethodOptions);

    // =========================================================
    //  Outputs
    // =========================================================

    new cdk.CfnOutput(this, "ApiGatewayUrl", {
      value: this.api.url,
      description: "AETHER REST API Gateway URL",
    });

    new cdk.CfnOutput(this, "SnsTopicArn", {
      value: this.alertsTopic.topicArn,
      description: "AETHER Alerts SNS Topic ARN",
    });

    new cdk.CfnOutput(this, "EventProcessorArn", {
      value: this.eventProcessorFn.functionArn,
    });

    new cdk.CfnOutput(this, "EscalationHandlerArn", {
      value: this.escalationHandlerFn.functionArn,
    });

    new cdk.CfnOutput(this, "TimelineAggregatorArn", {
      value: this.timelineAggregatorFn.functionArn,
    });

    new cdk.CfnOutput(this, "CareNavigationArn", {
      value: this.careNavigationFn.functionArn,
    });

    new cdk.CfnOutput(this, "ApiHandlerArn", {
      value: this.apiHandlerFn.functionArn,
    });

    new cdk.CfnOutput(this, "FallDetectionWorkflowArn", {
      value: this.fallDetectionWorkflow.stateMachineArn,
    });

    new cdk.CfnOutput(this, "MedicationAdherenceWorkflowArn", {
      value: this.medicationAdherenceWorkflow.stateMachineArn,
    });
  }

  /**
   * Load a Step Functions ASL definition and substitute placeholder ARNs
   * with the actual Lambda function ARNs from this stack.
   */
  private loadStepFunctionDefinition(filePath: string): string {
    const fs = require("fs");
    let definition = fs.readFileSync(filePath, "utf-8");

    // Replace placeholder ARNs with constructed ARNs (not resource token refs)
    // This avoids circular dependencies between Lambda ↔ Step Functions
    const region = cdk.Aws.REGION;
    const account = cdk.Aws.ACCOUNT_ID;

    const replacements: Record<string, string> = {
      "aether-event-processor": `arn:aws:lambda:${region}:${account}:function:aether-event-processor`,
      "aether-escalation-handler": `arn:aws:lambda:${region}:${account}:function:aether-escalation-handler`,
      "aether-timeline-aggregator": `arn:aws:lambda:${region}:${account}:function:aether-timeline-aggregator`,
      "aether-care-navigation": `arn:aws:lambda:${region}:${account}:function:aether-care-navigation`,
      "aether-api-handler": `arn:aws:lambda:${region}:${account}:function:aether-api-handler`,
    };

    for (const [fnName, arn] of Object.entries(replacements)) {
      const pattern = new RegExp(
        `arn:aws:lambda:\\$\\{AWS::Region\\}:\\$\\{AWS::AccountId\\}:function:${fnName}`,
        "g"
      );
      definition = definition.replace(pattern, arn);
    }

    definition = definition.replace(
      /arn:aws:sns:\$\{AWS::Region\}:\$\{AWS::AccountId\}:aether-alerts/g,
      `arn:aws:sns:${region}:${account}:aether-alerts`
    );

    return definition;
  }
}

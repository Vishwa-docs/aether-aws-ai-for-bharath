#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { StorageStack } from "../lib/storage-stack";
import { IotStack } from "../lib/iot-stack";
import { AuthStack } from "../lib/auth-stack";
import { LambdaApiStack } from "../lib/lambda-api-stack";

const app = new cdk.App();

const env: cdk.Environment = {
  account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT_ID,
  region: process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || "ap-south-1",
};

// Day 2: DynamoDB tables + S3 buckets
const storageStack = new StorageStack(app, "AetherStorageStack", {
  env,
  description: "AETHER - DynamoDB tables and S3 buckets",
});

// Day 3: IoT Core resources
const iotStack = new IotStack(app, "AetherIotStack", {
  env,
  description: "AETHER - IoT Core thing types, thing groups, and policies",
});

// Day 9: Cognito authentication
const authStack = new AuthStack(app, "AetherAuthStack", {
  env,
  description: "AETHER - Cognito User Pool, App Clients, and Identity Pool",
});

// Day 4-5: Lambda functions, API Gateway, Step Functions
const lambdaApiStack = new LambdaApiStack(app, "AetherLambdaApiStack", {
  env,
  description: "AETHER - Lambda functions, API Gateway, and Step Functions",
  eventsTable: storageStack.eventsTable,
  timelineTable: storageStack.timelineTable,
  residentsTable: storageStack.residentsTable,
  consentTable: storageStack.consentTable,
  clinicOpsTable: storageStack.clinicOpsTable,
  evidenceBucket: storageStack.evidenceBucket,
  modelsBucket: storageStack.modelsBucket,
  userPool: authStack.userPool,
});

// Tag everything
cdk.Tags.of(app).add("Project", "AETHER");
cdk.Tags.of(app).add("Environment", "dev");

import * as cdk from "aws-cdk-lib";
import * as iot from "aws-cdk-lib/aws-iot";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

/**
 * IotStack — Day 3
 *
 * Creates IoT Core thing types, thing groups, and policies
 * for the AETHER device fleet.
 */
export class IotStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================
    //  Thing Types
    // =========================================================

    const edgeGatewayType = new iot.CfnThingType(this, "EdgeGatewayType", {
      thingTypeName: "AetherEdgeGateway",
      thingTypeProperties: {
        thingTypeDescription: "AETHER Edge Gateway (Jetson Orin Nano / RPi5)",
        searchableAttributes: ["home_id", "firmware_version", "hardware_type"],
      },
    });

    const acousticSentinelType = new iot.CfnThingType(this, "AcousticSentinelType", {
      thingTypeName: "AetherAcousticSentinel",
      thingTypeProperties: {
        thingTypeDescription: "AETHER Acoustic Sentinel (ESP32 MCU)",
        searchableAttributes: ["home_id", "room", "firmware_version"],
      },
    });

    const wearableType = new iot.CfnThingType(this, "WearableType", {
      thingTypeName: "AetherWearable",
      thingTypeProperties: {
        thingTypeDescription: "AETHER Wearable IMU (Pendant / Wristband)",
        searchableAttributes: ["home_id", "resident_id", "device_model"],
      },
    });

    // =========================================================
    //  Thing Groups
    // =========================================================

    const deviceGroup = new iot.CfnThingGroup(this, "DeviceGroup", {
      thingGroupName: "aether-devices",
      thingGroupProperties: {
        thingGroupDescription: "All AETHER devices",
      },
    });

    const edgeGatewayGroup = new iot.CfnThingGroup(this, "EdgeGatewayGroup", {
      thingGroupName: "aether-edge-gateways",
      parentGroupName: "aether-devices",
      thingGroupProperties: {
        thingGroupDescription: "AETHER Edge Gateways",
      },
    });
    edgeGatewayGroup.addDependency(deviceGroup);

    const sentinelGroup = new iot.CfnThingGroup(this, "SentinelGroup", {
      thingGroupName: "aether-acoustic-sentinels",
      parentGroupName: "aether-devices",
      thingGroupProperties: {
        thingGroupDescription: "AETHER Acoustic Sentinels",
      },
    });
    sentinelGroup.addDependency(deviceGroup);

    const wearableGroup = new iot.CfnThingGroup(this, "WearableGroup", {
      thingGroupName: "aether-wearables",
      parentGroupName: "aether-devices",
      thingGroupProperties: {
        thingGroupDescription: "AETHER Wearable IMU devices",
      },
    });
    wearableGroup.addDependency(deviceGroup);

    // =========================================================
    //  IoT Policy — scoped MQTT topics
    // =========================================================

    const devicePolicy = new iot.CfnPolicy(this, "DevicePolicy", {
      policyName: "AetherDevicePolicy",
      policyDocument: {
        Version: "2012-10-17",
        Statement: [
          {
            Effect: "Allow",
            Action: "iot:Connect",
            Resource: `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:client/\${iot:Connection.Thing.ThingName}`,
          },
          {
            Effect: "Allow",
            Action: "iot:Publish",
            Resource: [
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/aether/+/events`,
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/aether/+/telemetry`,
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/aether/+/status`,
            ],
          },
          {
            Effect: "Allow",
            Action: "iot:Subscribe",
            Resource: [
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topicfilter/aether/+/commands`,
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topicfilter/aether/+/config`,
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topicfilter/aether/+/ota`,
            ],
          },
          {
            Effect: "Allow",
            Action: "iot:Receive",
            Resource: [
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/aether/+/commands`,
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/aether/+/config`,
              `arn:aws:iot:${cdk.Aws.REGION}:${cdk.Aws.ACCOUNT_ID}:topic/aether/+/ota`,
            ],
          },
        ],
      },
    });

    // =========================================================
    //  MQTT Topic Rules (route events to future Lambda)
    // =========================================================

    // Placeholder rule — logs to CloudWatch for now; Lambda target added in Day 8
    const eventLogRule = new iot.CfnTopicRule(this, "EventLogRule", {
      ruleName: "AetherEventLog",
      topicRulePayload: {
        description: "Log all AETHER events to CloudWatch (placeholder until Lambda is ready)",
        sql: "SELECT * FROM 'aether/+/events'",
        awsIotSqlVersion: "2016-03-23",
        ruleDisabled: false,
        actions: [
          {
            cloudwatchLogs: {
              logGroupName: "/aether/iot-events",
              roleArn: this.createIotLogRole().roleArn,
              batchMode: false,
            },
          },
        ],
      },
    });

    // =========================================================
    //  Outputs
    // =========================================================
    new cdk.CfnOutput(this, "DevicePolicyName", { value: devicePolicy.policyName! });
    new cdk.CfnOutput(this, "DeviceGroupName", { value: deviceGroup.thingGroupName! });
    new cdk.CfnOutput(this, "EdgeGatewayTypeName", { value: edgeGatewayType.thingTypeName! });
  }

  /** Create an IAM role that lets IoT Core write to CloudWatch Logs */
  private createIotLogRole(): iam.Role {
    const role = new iam.Role(this, "IotLogRole", {
      roleName: "AetherIotCloudWatchRole",
      assumedBy: new iam.ServicePrincipal("iot.amazonaws.com"),
    });
    role.addToPolicy(
      new iam.PolicyStatement({
        actions: [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ],
        resources: ["arn:aws:logs:*:*:log-group:/aether/*"],
      })
    );
    return role;
  }
}

import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import * as iam from "aws-cdk-lib/aws-iam";
import { Construct } from "constructs";

/**
 * AuthStack — Day 9
 *
 * Creates Cognito User Pool, App Clients, and Identity Pool
 * for caregiver/nurse/admin authentication.
 */
export class AuthStack extends cdk.Stack {
  public readonly userPool: cognito.UserPool;
  public readonly webClient: cognito.UserPoolClient;
  public readonly mobileClient: cognito.UserPoolClient;
  public readonly identityPool: cognito.CfnIdentityPool;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // =========================================================
    //  Cognito User Pool
    // =========================================================

    this.userPool = new cognito.UserPool(this, "AetherUserPool", {
      userPoolName: "aether-user-pool",
      selfSignUpEnabled: false, // Admin-only registration for safety
      signInAliases: {
        email: true,
        phone: true,
      },
      autoVerify: {
        email: true,
        phone: true,
      },
      standardAttributes: {
        email: { required: true, mutable: true },
        fullname: { required: true, mutable: true },
        phoneNumber: { required: false, mutable: true },
      },
      customAttributes: {
        role: new cognito.StringAttribute({
          minLen: 1,
          maxLen: 50,
          mutable: true,
        }),
        home_ids: new cognito.StringAttribute({
          minLen: 0,
          maxLen: 2048,
          mutable: true,
        }),
        clinic_id: new cognito.StringAttribute({
          minLen: 0,
          maxLen: 128,
          mutable: true,
        }),
      },
      passwordPolicy: {
        minLength: 12,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: true,
        tempPasswordValidity: cdk.Duration.days(7),
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_AND_PHONE_WITHOUT_MFA,
      mfa: cognito.Mfa.OPTIONAL,
      mfaSecondFactor: {
        sms: true,
        otp: true,
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // =========================================================
    //  User Pool Groups (RBAC)
    // =========================================================

    new cognito.CfnUserPoolGroup(this, "AdminGroup", {
      groupName: "admin",
      userPoolId: this.userPool.userPoolId,
      description: "System administrators",
      precedence: 0,
    });

    new cognito.CfnUserPoolGroup(this, "NurseGroup", {
      groupName: "nurse",
      userPoolId: this.userPool.userPoolId,
      description: "Professional nurses with clinical access",
      precedence: 1,
    });

    new cognito.CfnUserPoolGroup(this, "CaregiverGroup", {
      groupName: "caregiver",
      userPoolId: this.userPool.userPoolId,
      description: "Family caregivers with resident access",
      precedence: 2,
    });

    new cognito.CfnUserPoolGroup(this, "ClinicManagerGroup", {
      groupName: "clinic_manager",
      userPoolId: this.userPool.userPoolId,
      description: "B2B clinic operations managers",
      precedence: 1,
    });

    // =========================================================
    //  App Clients
    // =========================================================

    // Web Dashboard Client (SPA — no secret)
    this.webClient = this.userPool.addClient("WebClient", {
      userPoolClientName: "aether-web-dashboard",
      generateSecret: false,
      authFlows: {
        userSrp: true,
        userPassword: false,
        custom: true,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true, implicitCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
        callbackUrls: [
          "http://localhost:3000/callback",
          "https://app.aether.care/callback",
        ],
        logoutUrls: [
          "http://localhost:3000/",
          "https://app.aether.care/",
        ],
      },
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(30),
      preventUserExistenceErrors: true,
    });

    // Mobile App Client
    this.mobileClient = this.userPool.addClient("MobileClient", {
      userPoolClientName: "aether-mobile-app",
      generateSecret: true,
      authFlows: {
        userSrp: true,
        custom: true,
      },
      oAuth: {
        flows: { authorizationCodeGrant: true },
        scopes: [cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
        callbackUrls: ["aether://callback"],
        logoutUrls: ["aether://logout"],
      },
      accessTokenValidity: cdk.Duration.hours(1),
      idTokenValidity: cdk.Duration.hours(1),
      refreshTokenValidity: cdk.Duration.days(90),
      preventUserExistenceErrors: true,
    });

    // Edge Gateway Client (Machine-to-machine)
    const edgeClient = this.userPool.addClient("EdgeClient", {
      userPoolClientName: "aether-edge-gateway",
      generateSecret: true,
      authFlows: {
        userSrp: true,
        custom: true,
      },
      accessTokenValidity: cdk.Duration.hours(12),
      idTokenValidity: cdk.Duration.hours(12),
      refreshTokenValidity: cdk.Duration.days(365),
      preventUserExistenceErrors: true,
    });

    // =========================================================
    //  User Pool Domain (Hosted UI)
    // =========================================================

    this.userPool.addDomain("AetherDomain", {
      cognitoDomain: {
        domainPrefix: `aether-${cdk.Aws.ACCOUNT_ID}`,
      },
    });

    // =========================================================
    //  Identity Pool (for AWS credential vending)
    // =========================================================

    this.identityPool = new cognito.CfnIdentityPool(this, "AetherIdentityPool", {
      identityPoolName: "aether_identity_pool",
      allowUnauthenticatedIdentities: false,
      cognitoIdentityProviders: [
        {
          clientId: this.webClient.userPoolClientId,
          providerName: this.userPool.userPoolProviderName,
        },
        {
          clientId: this.mobileClient.userPoolClientId,
          providerName: this.userPool.userPoolProviderName,
        },
      ],
    });

    // Authenticated role
    const authenticatedRole = new iam.Role(this, "CognitoAuthRole", {
      roleName: "AetherCognitoAuthRole",
      assumedBy: new iam.FederatedPrincipal(
        "cognito-identity.amazonaws.com",
        {
          StringEquals: {
            "cognito-identity.amazonaws.com:aud": this.identityPool.ref,
          },
          "ForAnyValue:StringLike": {
            "cognito-identity.amazonaws.com:amr": "authenticated",
          },
        },
        "sts:AssumeRoleWithWebIdentity"
      ),
    });

    // Authenticated users can invoke API Gateway
    authenticatedRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["execute-api:Invoke"],
        resources: ["*"],
      })
    );

    // Attach role to identity pool
    new cognito.CfnIdentityPoolRoleAttachment(this, "IdentityPoolRoles", {
      identityPoolId: this.identityPool.ref,
      roles: {
        authenticated: authenticatedRole.roleArn,
      },
    });

    // =========================================================
    //  Outputs
    // =========================================================

    new cdk.CfnOutput(this, "UserPoolId", {
      value: this.userPool.userPoolId,
      description: "Cognito User Pool ID",
    });

    new cdk.CfnOutput(this, "UserPoolArn", {
      value: this.userPool.userPoolArn,
      description: "Cognito User Pool ARN",
    });

    new cdk.CfnOutput(this, "WebClientId", {
      value: this.webClient.userPoolClientId,
      description: "Web Dashboard App Client ID",
    });

    new cdk.CfnOutput(this, "MobileClientId", {
      value: this.mobileClient.userPoolClientId,
      description: "Mobile App Client ID",
    });

    new cdk.CfnOutput(this, "EdgeClientId", {
      value: edgeClient.userPoolClientId,
      description: "Edge Gateway App Client ID",
    });

    new cdk.CfnOutput(this, "IdentityPoolId", {
      value: this.identityPool.ref,
      description: "Cognito Identity Pool ID",
    });

    new cdk.CfnOutput(this, "AuthDomain", {
      value: `aether-${cdk.Aws.ACCOUNT_ID}.auth.${cdk.Aws.REGION}.amazoncognito.com`,
      description: "Cognito Hosted UI Domain",
    });
  }
}

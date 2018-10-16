import * as CleanWebpackPlugin from "clean-webpack-plugin";
import * as HtmlWebpackPlugin from "html-webpack-plugin";
import * as MiniCssExtractPlugin from "mini-css-extract-plugin";
import * as OptimizeCSSAssetsPlugin from "optimize-css-assets-webpack-plugin";
import * as UglifyJsPlugin from "uglifyjs-webpack-plugin";
import * as webpack from "webpack";

const config: webpack.Configuration = {
  entry: __dirname + "/src/Ranking.ts",
  output: {
    path: __dirname + "/dist",
    filename: "js/[name].[contenthash].js"
  },
  resolve: {
    extensions: [".ts", ".tsx", ".js", ".jsx", ".css"],
  },
  module: {
    rules: [
      { test: /\.html$/, loader: 'html-loader' },
      {
        test: /\.(jsx?|tsx?)$/,
        exclude: /node_modules/,
        use: "babel-loader"
      },
      {
        test: /\.css$/,
        use: [
          MiniCssExtractPlugin.loader,
          "css-loader"
        ]
      },
      {
        test: /\.(png|ico)$/,
        use: [
          {
            loader: "url-loader",
            options: {
              limit: 5000,
              name: 'img/[name].[ext]'
            }
          }
        ]
      }
    ]
  },
  optimization: {
    runtimeChunk: "single",
    splitChunks: {
      cacheGroups: {
        vendor: {
          test: /node_modules/,
          name: 'vendors',
          chunks: 'all'
        }
      }
    },
    minimizer: [
      new UglifyJsPlugin({
        cache: true,
        parallel: true,
        sourceMap: true,
        uglifyOptions: {
          compress: {
            "dead_code": true
          }
        }
      }),
      new OptimizeCSSAssetsPlugin({})
    ]
  },
  plugins: [
    new webpack.HashedModuleIdsPlugin(),
    new CleanWebpackPlugin(["dist"]),
    new HtmlWebpackPlugin({
      template: "Ranking.html"
    }),
    new MiniCssExtractPlugin({
      filename: "css/[name].[contenthash].css"
    })
  ]
};

export default config;
